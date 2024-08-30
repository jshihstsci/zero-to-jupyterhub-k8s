"""Top level library module providing spawner a one-stop-shop i/f to uid/gid

Provides the main entrypoint of the uid/gid system.  It takes
the inputs about the user and returns the outputs needed to spawn a user
within a notebook container and fully identify them within the context of the
Ubuntu system.
"""

import os
import subprocess
from pathlib import Path
import stat

# from shutil import chown
import json

import uuid
from uidgid.types import StsciUuid, StsciEzid, TeamName, GroupName, UserName
from uidgid.types import Uid, UserGid, GroupAdminUid, GroupGid
from uidgid.types import UidGidInputs, SpawnInfo
from uidgid import users
from uidgid import groups
from uidgid.log import Log
from uidgid import backup

import filelock


# -----------------------------------------------------------------------------------------
#                                Globals
# -----------------------------------------------------------------------------------------
TEAMS_ROOT_DIR = Path("/teams")  # For creating team dirs
HOME_ROOT_DIR = Path("/users")  # For creating $HOME dirs
UID_GID_ROOT_DIR = Path("/services/uidgid")  # For rosetta tables persistence
BACKUPS_ROOT_DIR = Path("/backups/uidgid")  # rosetta backup in alternate dir

SVC_UID = os.environ.get("SVC_UID", "1000")
SVC_GID = os.environ.get("SVC_GID", "1000")


# -----------------------------------------------------------------------------------------


def run(cmd, cwd=".", timeout=30, check=True):
    """Run subprocess `cmd` in dir `cwd` failing if not completed within `timeout` seconds
    of if `cmd` returns a non-zero exit status.

    Returns both stdout+stderr from `cmd`.  (untested, verify manually if in doubt)
    """
    return subprocess.run(
        cmd.split(),
        capture_output=True,
        text=True,
        check=check,
        cwd=cwd,
        timeout=timeout,
    )  # maybe succeeds


def chown(path, uid, gid, timeout=30, sudo="/usr/bin/sudo /usr/bin/"):
    """Run subprocess `chown` in dir `cwd` failing if not completed within `timeout` seconds
    of if `chown` returns a non-zero exit status.
    """
    sudo = "/usr/bin/sudo /usr/bin/" if os.environ.get("USE_SUDO") == "1" else ""
    return run(f"{sudo}chown -R {uid}:{gid} {path}", timeout=timeout)


# -----------------------------------------------------------------------------------------
#                  API Class Implementing High Level Functions of UIDGID
# -----------------------------------------------------------------------------------------


class UidGidApi:
    """Maintains copies of users and groups in memory,  as well as a log
    interface and a lock to ensure that multiple spawners are not modifying
    the file store at the same time.
    """

    def __init__(self):
        self.users = users.Users(yaml_filename=UID_GID_ROOT_DIR / "all_users.yaml")
        self.groups = groups.Groups(yaml_filename=UID_GID_ROOT_DIR / "all_groups.yaml")
        self.log = Log("uidgid")
        self.lock = filelock.FileLock(UID_GID_ROOT_DIR / "uidgid.lock")

    @property
    def all_names(self) -> set[str]:
        """Return the set of all user and group names in the system."""
        self.users.load_all_usernames()
        self.groups.load_all_groupnames()
        return set(
            str(name)
            for name in set(self.users.all_usernames) | set(self.groups.all_groupnames)
        )

    # Note that even as a library vs. service call the Spawner itself
    # is running in the context of hypercorn coroutines and surrender
    # of the active thread to other co-routines during library calls
    # where it may not be obvious is possible.   Locking can be used
    # to ensure that no other spawners are running at the same time
    # the file store is modified.

    def get_spawn_info(
        self,
        stsci_uuid: StsciUuid,
        stsci_ezid: StsciEzid,
        active_team: TeamName,
        teams: list[TeamName],
    ) -> SpawnInfo:
        """Given upstream identities from Cognito/AD/ADX/Proper,   dynamically create
        and/or fetch their corresponding Ubuntu identities which consist of compliant
        user and group names and their respective uid/gid values.  Additionally,
        return strings containing the /etc/passwd and /etc/group contents which
        UNIX uses to track all users and groups.
        """
        try:
            stsci_uuid = StsciUuid(stsci_uuid)
            stsci_ezid = StsciEzid(stsci_ezid)
            active_team = TeamName(active_team)
            teams = [TeamName(team) for team in teams]
        except Exception as e:
            self.log.exception("UIDGID invalid parameter:", e)
            raise
        try:
            self.lock.acquire(blocking=True)
            return self._locked_get_spawn_info(
                stsci_uuid, stsci_ezid, active_team, teams
            )
        except Exception as e:
            self.log.exception("UIDGID Exception fetching spawn info:", e)
            raise
        finally:
            self.lock.release()

    def _locked_get_spawn_info(
        self,
        stsci_uuid: StsciUuid,
        stsci_ezid: StsciEzid,
        active_team: TeamName,
        teams: list[TeamName],
    ) -> SpawnInfo:
        self.log.info(
            "Called:", UidGidInputs(stsci_uuid, stsci_ezid, active_team, teams)
        )

        # check for user does not exist,  add user, add personal group
        username, uid = self.create_or_fetch_user(stsci_uuid, stsci_ezid)

        # Handle creation of specified team groups, their admin users, and team
        # memberships for both the user and group's admin user.
        for teamname in teams:
            self.create_or_fetch_group(username, teamname)

        # Spawner defines truth,  if team name not listed,  remove user from team.
        self.remove_obsolete_group_memberships(username, teams)

        # Ensure user actually is in the active group.
        if active_team in teams + [TeamName(stsci_ezid)]:
            g_info = self.groups.get_group_info(active_team, id_type="teamname")
        else:
            raise ValueError(f"Active team {active_team} not in user's teams {teams}")

        # fetch user uid, active gid, etc_passwd, etc_group
        # user uid also determines the gid for their personal group.
        # active team's gid is also the uid for the admin-user of the active
        # team.
        all_user_gids = sorted(
            [
                self.groups.lookup_gid(groupname)
                for groupname in self.groups.get_groups_of_user(username)
            ]
        )
        info = SpawnInfo(
            uid,
            g_info.gid,
            all_user_gids,
            username,
            g_info.groupname,
            self.users.get_etc_passwd_string(),
            self.groups.get_etc_group_string(),
        )
        self.backup_rosetta_tables()
        self.log.info(f"Returning {info}\n")
        return info

    def create_or_fetch_user(
        self, stsci_uuid: StsciUuid, stsci_ezid: StsciEzid
    ) -> tuple[UserName, Uid]:
        """If the specified user does not exist,  create it.  If it does exist, fetch it.
        In addition to creating any user,  also create a personal group for the user and
        add them as a member of that group.
        """
        if not self.users.user_exist(stsci_uuid):
            user = self.users.add_user(
                stsci_uuid, stsci_ezid, existing_names=self.all_names
            )
            self.log.info(f"Added {repr(user)}.")
            personal_group = self.groups.create_new_group(
                teamname=TeamName(user.ezid),
                groupname=GroupName(user.username),
                usertype="individual",
                gid=UserGid(user.uid),
                existing_names=self.all_names,
            )
            self.log.info(f"Added personal {repr(personal_group)}.")
            self.add_member(UserName(user.username), personal_group.groupname)
            self.create_home_directory(user.username, user.uid)
        else:
            user = self.users.get_user_info(stsci_uuid, id_type="uuid")
            self.log.info(f"Fetched {repr(user)}.")
            personal_group = self.groups.get_group_info(
                id=GroupName(user.username), id_type="groupname"
            )
            self.log.info(f"Fetched personal {repr(personal_group)}.")
        return user.username, user.uid

    def create_or_fetch_group(self, username: UserName, teamname: TeamName) -> None:
        """If the group corresponding to `teamname` exists,  fetch it.  Else, create it.
        If a group is created,  also create a corresponding admin user and group directory.
        """
        if not self.groups.team_exist(teamname):
            group = self.groups.create_new_group(teamname=teamname, usertype="group")
            self.log.info(f"Added {repr(group)}.")
            admin_user = self.users.add_user(
                str(uuid.uuid4()),
                f"{group.groupname}-admin",
                uid=GroupAdminUid(group.gid),
                gid=GroupGid(group.gid),
                usertype="group",
                existing_names=self.all_names,
            )
            self.log.info(f"Added admin {repr(admin_user)}.")
            self.add_member(username, group.groupname)
            self.add_member(UserName(str(group.groupname) + "-admin"), group.groupname)
            self.create_group_directory(group.groupname, group.gid)
        else:
            group = self.groups.get_group_info(teamname, id_type="teamname")
            self.log.info(f"Fetched {repr(group)}.")
            if group.gid >= GroupGid.min_id:  # non-system / uidgid assigned groups only
                admin_user = self.users.get_user_info(
                    id=GroupAdminUid(group.gid), id_type="uid"
                )
                self.log.info(f"Fetched admin {repr(admin_user)}.")
            else:
                self.log.info(f"No admin user for {repr(group)}.")
            if username not in self.groups.get_users_of_group(group.groupname):
                self.add_member(username, group.groupname)

    def add_member(self, username: UserName, groupname: GroupName) -> None:
        """Add username to group groupname and log it."""
        self.groups.add_user_to_group(username, groupname)
        self.log.info(
            f"Added group member {repr(username)}: {repr(self.groups.get_group_info(groupname, id_type='groupname'))}"
        )

    def teamnames_to_groupnames(self, teamnames: list[TeamName]) -> list[GroupName]:
        """Convert a list of teamnames to a list of groupnames."""
        return [
            self.groups.get_group_info(teamname, id_type="teamname").groupname
            for teamname in teamnames
        ]

    def remove_obsolete_group_memberships(
        self, username: UserName, team_names: list[TeamName]
    ) -> None:
        """Remove any group memberships for which the user is not a member of the
        corresponding team.
        """
        group_names = self.groups.get_groups_of_user(username)
        team_groups = self.teamnames_to_groupnames(team_names)
        for groupname in group_names:
            if groupname not in team_groups + [GroupName(username)]:
                self.remove_member(username, groupname)

    def remove_member(self, username: UserName, groupname: GroupName) -> None:
        """Remove username from group groupname and log it."""
        self.groups.remove_user_from_group(username=username, groupname=groupname)
        self.log.info(
            f"Removed group member {repr(username)}: {repr(self.groups.get_group_info(groupname, id_type='groupname'))}"
        )

    # ............................... directory creation .......................................

    def create_group_directory(self, groupname: GroupName, gid: int) -> None:
        """Do whatever is required  to set up a new group directory with the
        correct ownership, permissions, special bits, and structure.  Goals:
        /teams            root:root                 rwxr-xr-x  new teams space for all groups/teams
        /teams/groupname  groupname-admin:groupname rwxrws--T  setgid, sticky, all user, all group, no other
        """
        # Ensure root owned teams dir exists with correct perms
        if not TEAMS_ROOT_DIR.exists():
            self.log.info(f"Creating teams directory {TEAMS_ROOT_DIR}")
            TEAMS_ROOT_DIR.mkdir()
            # set permissions:  setgid, sticky, all user, all group, no other
            TEAMS_ROOT_DIR.chmod(
                stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH
            )
            chown(TEAMS_ROOT_DIR, SVC_UID, SVC_GID)  # for clarity,  really implied
        group_dir = TEAMS_ROOT_DIR / groupname
        # make group directory
        if not group_dir.exists():
            self.log.info(f"Creating directory for group {groupname} at {group_dir}")
            group_dir.mkdir(exist_ok=True)
            # make group admin directory
            self.create_home_directory(f"{groupname}-admin", gid)
            # set permissions:  setgid, sticky, all user, all group, no other
            group_dir.chmod(stat.S_ISGID | stat.S_ISVTX | stat.S_IRWXU | stat.S_IRWXG)
            # set ownership: group-admin:group
            chown(group_dir, gid, gid)  # must be root

    def create_home_directory(self, username: str, uid: int) -> None:
        """Create a home directory for the user.   Goals:
        /users           root:root         rwxr-xr-x  all user
        /users/username  username:username rwxr-x---  all user, group rx, other none
        """
        if not HOME_ROOT_DIR.exists():
            self.log.warning(f"Creating home root directory {HOME_ROOT_DIR}")
            HOME_ROOT_DIR.mkdir(parents=True)
            HOME_ROOT_DIR.chmod(
                stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH
            )  # rwxr-xr-x,  no special
            chown(HOME_ROOT_DIR, SVC_UID, SVC_GID)  # for clarity,  really implied
        home_dir = HOME_ROOT_DIR / username
        if not home_dir.exists():
            self.log.info(f"Creating home directory for {username} at {home_dir}")
            home_dir.mkdir()
            home_dir.chmod(
                stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP
            )  # user all perms,  group read/execute, other no perms,  no special bits
            self.create_teams_symlnk(username)
            chown(home_dir, uid, uid)  # must be root to chown

    def create_teams_symlnk(self, username: str) -> None:
        """
        Create a symbolic link for the "teams" directory in the user's home
        directory, pointing to the global "/teams" directory.  This allows users
        to easily access the shared "teams" directory from their home directory
        using the JH file browser.
        """
        teams_link = HOME_ROOT_DIR / username / "teams"
        if not teams_link.is_symlink():
            self.log.info(
                f"Creating symlnk for {username} from {teams_link} --> {TEAMS_ROOT_DIR}"
            )
            teams_link.symlink_to(TEAMS_ROOT_DIR, target_is_directory=True)

    def check_teams_dir(self, check_ownership: bool = True) -> None:
        assert TEAMS_ROOT_DIR.exists()
        if check_ownership:
            assert TEAMS_ROOT_DIR.owner() == "root"
            assert TEAMS_ROOT_DIR.group() == "root"
        dir_stat = TEAMS_ROOT_DIR.stat()
        assert dir_stat.st_mode & stat.S_IRWXU == stat.S_IRWXU  # all user
        assert dir_stat.st_mode & stat.S_IRGRP == stat.S_IRGRP  # group read
        assert dir_stat.st_mode & stat.S_IXGRP == stat.S_IXGRP  # group execute
        assert dir_stat.st_mode & stat.S_IROTH == stat.S_IROTH  # other read
        assert dir_stat.st_mode & stat.S_IXOTH == stat.S_IXOTH  # other execute
        assert not dir_stat.st_mode & (
            stat.S_ISUID | stat.S_ISGID | stat.S_ISVTX
        )  # no special: setgid, sticky, setuid

    def check_group_dir(
        self, groupname: GroupName, check_ownership: bool = True
    ) -> None:
        group_dir = TEAMS_ROOT_DIR / groupname
        assert group_dir.exists()
        if check_ownership:
            assert group_dir.owner() == f"{groupname}-admin"
            assert group_dir.group() == groupname
        dir_stat = group_dir.stat()
        assert dir_stat.st_mode & stat.S_IRWXU == stat.S_IRWXU  # all user
        assert dir_stat.st_mode & stat.S_IRWXG == stat.S_IRWXG  # all group
        assert dir_stat.st_mode & stat.S_IRWXO == 0  # no other
        assert dir_stat.st_mode & stat.S_ISGID == stat.S_ISGID  # setgid
        assert dir_stat.st_mode & stat.S_ISVTX == stat.S_ISVTX  # sticky
        assert not dir_stat.st_mode & stat.S_ISUID  # no setuid

    def check_home_dir(self, username: UserName, check_ownership: bool = True) -> None:
        home_dir = HOME_ROOT_DIR / username
        assert home_dir.exists()
        if check_ownership:
            assert home_dir.owner() == username
            assert home_dir.group() == username  # personal group
        dir_stat = home_dir.stat()
        assert dir_stat.st_mode & stat.S_IRWXU == stat.S_IRWXU  # all user
        assert dir_stat.st_mode & stat.S_IRWXG == (
            stat.S_IRGRP | stat.S_IXGRP
        )  # group read
        assert dir_stat.st_mode & stat.S_IRWXO == 0  # no other
        assert not dir_stat.st_mode & (
            stat.S_ISUID | stat.S_ISGID | stat.S_ISVTX
        )  # no special: setgid, sticky, setuid

    # ............................... Rosetta Backup .......................................

    def backup_rosetta_tables(self) -> None:
        """When called this function will backup the information in the Rosetta
        tables in case they are later corrupted or lost somehow.

        Locking from get_spawn_info() is assumed here.
        """
        self.backup_rosetta_using_log()
        self.backup_rosetta_using_files()

    def backup_rosetta_using_log(self) -> None:
        """When called this function will backup the information in the Rosetta
        tables in case they are later corrupted or lost somehow.
        """
        try:
            user_blob = backup.encode_from_file(self.users.yaml_filename)
            group_blob = backup.encode_from_file(self.groups.yaml_filename)
            self.log.info(
                "Uid/gid rosetta backup as log event",
                user_rosetta=user_blob,
                group_rosetta=group_blob,
                dd_mode=True,
            )
        except Exception as exc:
            self.log.exception(exc, "Rosetta table log backups FAILED.")

    def backup_rosetta_using_files(self) -> None:
        """Copy rosetta table files to an EFS backup directory."""
        try:
            backup.backup_file(self.users.yaml_filename, BACKUPS_ROOT_DIR)
            backup.backup_file(self.groups.yaml_filename, BACKUPS_ROOT_DIR)
            self.log.info(f"Uid/gid rosetta backup files to {BACKUPS_ROOT_DIR}")
        except Exception as exc:
            self.log.exception(exc, "Rosetta table backup files FAILED.")

    # ...............................................................................

    def locked_restore_rosetta_files(self, event: str) -> None:
        """When called this function will restore the information in the Rosetta
        tables from a backup.   This wrapper just handles locking to prevent
        simultaneous mods to the Rosetta tables by different processes/agents.
        """
        with self.lock.acquire(blocking=True):
            try:
                self._unlocked_restore_rosetta_files(event)
            finally:
                self.lock.release()

    def _unlocked_restore_rosetta_files(self, event: str) -> None:
        """When called this function will restore the information in the Rosetta
        tables from a backup.   After restoring,  issues a new backup event
        reflecting the restored state.
        """
        event_json = json.loads(event)
        user_blob = event_json["user_rosetta"]
        group_blob = event_json["group_rosetta"]
        backup.decode_to_file(self.users.yaml_filename, user_blob)
        backup.decode_to_file(self.groups.yaml_filename, group_blob)


# -----------------------------------------------------------------------------------------
#                            API Singleton and Convenience Functions
# -----------------------------------------------------------------------------------------

UID_GID_API: UidGidApi | None = None


def init_api(reinit: bool = True) -> UidGidApi:
    """Initialize the UidGidApi singleton."""
    global UID_GID_API
    if reinit or not UID_GID_API:
        UID_GID_API = UidGidApi()
    return UID_GID_API


def get_spawn_info(
    stsci_uuid: StsciUuid,
    stsci_ezid: StsciEzid,
    active_team: TeamName,
    teams: list[TeamName],
) -> SpawnInfo:
    """Simple function interface for Spawner to get spawn info."""
    api = init_api(reinit=False)
    return api.get_spawn_info(stsci_uuid, stsci_ezid, active_team, teams)

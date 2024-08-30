"""This module defines basic types for uid/gid trying to formalize
some of the subtle distinctions between different kinds of identifiers
and ids.
"""

import re
from dataclasses import dataclass
from collections.abc import Sequence

# -----------------------------------------------------------------------------------------
#                                inputs
# -----------------------------------------------------------------------------------------


class StrComparable(str):
    """Base class for making str subclasses comparable to themselves or str
    instances.   Note that intentionally not even subclasses are comparable,
    only a class and str.
    """

    def _check_class(self, other):
        """Comparable if type(other) is type(self) or str.   TypeError othewise."""
        if type(other) not in [str, type(None), type(self)]:
            raise TypeError(f"{type(self)} cannot be compared to {type(other)}.")

    def __eq__(self, other):
        self._check_class(other)
        return str(self) == str(other)

    def __hash__(self):
        return hash(str(self))


class StsciUuid(StrComparable):
    """The unique uuid assigned by AD/ADX for a user,  and identity
    which is unambigous and equivalent to a name, best for internal
    non-user-facing usage.

    UUIDs are constructed in a sequence of digits equal to 128 bits.
    The ID is in hexadecimal digits, meaning it uses the numbers 0
    through 9 and letters A through F (upper or lowercase). The
    hexadecimal digits aregrouped as 32 hexadecimal characters with
    four hyphens:
        XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX.
    We normalize to lowercase below.
    """

    def __new__(cls, uuid: str):
        if not isinstance(uuid, str):
            raise TypeError("Uuid is not a string.")
        uuid = uuid.strip().lower()
        if re.match(r"^[0-9a-z]{32}$", uuid):  # hyphenate all uuids
            uuid = "-".join(
                [uuid[:8], uuid[8:12], uuid[12:16], uuid[16:20], uuid[20:32]]
            )
        elif not re.match(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
            uuid,
        ):
            raise ValueError("Invalid UUID format.")
        return super().__new__(cls, uuid)


class UnicodeName(StrComparable):
    """Loose unicode identifiers are identifiers which can be specified
    with a wide range of unicode characters and with lengths > 32 characters.

    This makes them unacceptable to use as Ubuntu user or group names but
    also more potentially expressive than a simple ascii string.

    Name identifiers of all kinds received from systems upstream of JupyterHub
    should be assumed to be of this base type unless otherwise guaranteed
    by upstream interfaces.
    """

    def __new__(cls, name: str):
        if not isinstance(name, str):
            raise TypeError("Name is not a string")
        if len(name) >= 128:
            raise ValueError("Name is too long")
        sanitized = re.sub(r"['\"`;\(\)\<\>/\\=%&|!\{\}\[\]#*~$]*", "", name)
        return super().__new__(cls, sanitized)


class StsciEzid(UnicodeName):
    """The unique human readable name assigned by AD/ADX for a user, typically
    derived from the user's full name or e-mail somehow.   These have the
    key limitation that they must be squashed before use by Ubuntu.
    """


class TeamName(UnicodeName):
    """The human readable form of a team name from proper,  later squashed
    into an Ubuntu group name.
    """


# -----------------------------------------------------------------------------------------
#                                Integer Ids and Ranges
# -----------------------------------------------------------------------------------------


class RangedId(int):
    """Baseclass for all of the unix ids which are used in the uid/gid system,
    whether user or group.  This is a 16-bit integer but may be expandable to
    32-bits should 16-bits not be sufficient.

    I think we should keep this simple:

    1. Allocate ids from dedicated ranges as needed.
    2. +1 for each new Id.
    3. Never delete or re-use an Id,  just "deactivate" with a flag.
    4. Once a user exists,  they exist forever but can be deacticvated preventing use.
    5. Once a group exists, it exists forever but can be deactivated preventing use.
    """

    min_id: int | None = None
    max_id: int | None = None

    def __new__(cls, value):
        cls.validate(value)
        return super().__new__(cls, value)

    @classmethod
    def validate(cls, value):
        if not isinstance(value, int):
            raise TypeError("Value is not an integer")
        if value < cls.min_id or value > cls.max_id:
            raise ValueError(
                f"Value is not in the valid range {cls.min_id} to {cls.max_id}"
            )


class Uid(RangedId):
    """ID corresponding to a user defined in /etc/passwd."""


class Gid(RangedId):
    """ID corresponding to a group defined in /etc/group."""


class SystemUid(Uid):
    """Uid for pre-defined system users,  e.g. root.""" ""

    min_id = 0
    max_id = 999


class SystemGid(Gid):
    """Gid for pre-defined system groups,  e.g. docker or admin."""

    min_id = 0
    max_id = 999


class UserUid(Uid):
    """Uid for a nominal human user added by JupyterHub."""

    min_id = 1000
    max_id = 59999


class UserGid(Gid):
    """Group of same name and ID as a nominal human user, often
    used as their default group for file creation and implicitly
    created whenever a new user is added.
    """

    min_id = 1000
    max_id = 59999


class GroupGid(Gid):
    """Gid for nominal JupyterHub added group,  typically for a team."""

    min_id = 60000
    max_id = 65533


class GroupAdminUid(Uid):
    """
    Uid for a pseudo-user which is given full ownership of team files to act
    as the team-admin.   The admin user should share the same name and id as
    the group.

    The admin pseudo-user is assumed at login rather than a user's personal
    identity when they are using the admin role of the team.

    Implicitly created whenever a new team/group is added and shared by all
    user's with the team admin role.
    """

    min_id = 60000
    max_id = 65533


# -----------------------------------------------------------------------------------------
#                                outputs
# -----------------------------------------------------------------------------------------


class UserStatus(str):
    """Users and Groups are never deleted but are tracked as 'active' or 'deactivated'."""

    valid_status = ["active", "deactivated"]

    def __new__(cls, status: str):
        assert isinstance(status, str), "Status is not a string."
        assert (
            status in cls.valid_status
        ), "Invalid status, must be 'active' or 'deactivated'"
        return str.__new__(cls, status)


class UserType(str):
    valid_type = ["individual", "group", "None"]

    def __new__(cls, usertype: str):
        assert isinstance(usertype, str), "User type is not a string."
        assert (
            usertype in cls.valid_type
        ), "Invalid user type, must be 'individual' or 'group'"
        return str.__new__(cls, usertype)


class UbuntuName(StrComparable):  # more generally UNIX name,  but check if not Ubuntu
    """User-facing name which is acceptable to use as a group or user name
    within Ubuntu UNIX for the purposes of the /etc/passwd and /etc/group
    files,  and any other places in Ubuntu a human readable user or group
    is needed,  e.g.  for the sudoers file or file system listings or API
    calls which utilize ASCII names vs. the corresponding id.
    """

    MAX_LEN: int = 32

    # From: https://systemd.io/USER_NAMES/#:~:text=Debian%2FUbuntu%20based%20systems%20enforce,the%20administrator%20at%20runtime%20though.
    @classmethod
    def is_valid(cls, name: str) -> bool:
        """Return True IFF `name` should work for Ubuntu user or group names.
        Take it slow to avoid possible attacks on checker functions.
        """
        return bool(
            isinstance(name, str)
            and len(name) <= cls.MAX_LEN
            and name.isascii()
            and re.match("^[a-z][a-z0-9-]{0,31}$", name)
        )

    def __new__(cls, value):
        if not cls.is_valid(value):
            raise ValueError(f"Value is not a valid Ubuntu user or group name: {value}")
        return super().__new__(cls, value)


class GroupName(UbuntuName):
    """Ubuntu group name."""


class UserName(UbuntuName):
    """Ubuntu user name."""


# -----------------------------------------------------------------------------------------
#                             Internal / Output Types
# -----------------------------------------------------------------------------------------


class User:
    # All user attributes, including UID/GID
    def __init__(
        self,
        username: UbuntuName | None = None,
        password: str | None = None,
        uid: UserUid | None = None,
        gid: UserGid | None = None,
        descr: str | None = None,
        home: str | None = None,
        shell: str | None = None,
        uuid: StsciUuid | None = None,
        ezid: StsciEzid | None = None,
        status: UserStatus | None = None,
        usertype: UserType | None = None,
    ):
        self.username = username
        self.password = password
        self.uid = uid
        self.gid = gid
        self.descr = descr
        self.home = home
        self.shell = shell
        self.uuid = uuid
        self.ezid = ezid
        self.status = status  # active, deactivated
        self.usertype = usertype  # individual, group

    def __str__(self):
        return f"{self.username}:{self.password}:{self.uid}:{self.gid}:{self.descr}:{self.home}:{self.shell}"

    def __repr__(self):
        return f"User(username={self.username}, uid={self.uid}, gid={self.gid}, uuid={self.uuid}, ezid={self.ezid}, status={self.status}, user_type={self.usertype})"


class Group:
    # All group attributes
    def __init__(
        self,
        teamname: UnicodeName | None = None,
        groupname: UbuntuName | None = None,
        password: str | None = None,
        gid: UserGid | None = None,
        grouplist: list | None = None,
        status: UserStatus | None = None,
        usertype: UserType | None = None,
    ):
        self.teamname = teamname
        self.groupname = groupname
        self.password = password
        self.gid = gid
        self.grouplist = grouplist or []
        self.status = status  # active, deactivated
        self.usertype = usertype  # individual, group

    def __str__(self):
        return f"{self.groupname}:{self.password}:{self.gid}:{','.join(self.grouplist)}"

    def __repr__(self):
        return f"Group(team_name={self.teamname}, group_name={self.groupname}, gid={self.gid}, group_list={repr(self.grouplist)}, status={self.status}, user_type={self.usertype})"


# -----------------------------------------------------------------------------------------
#                               Primary Service Inputs & Outputs
# -----------------------------------------------------------------------------------------


@dataclass
class UidGidInputs:
    """All of the inputs which are required to spawn a user based on interacting
    with the uid/gid system.   This includes information sufficient to automatically
    add users, groups, and group memberships to the uidgid system.  It also includes logic
    to automatically drop existing group memberships when a user is no longer a
    member of a team.
    """

    uuid: StsciUuid
    ezid: StsciEzid
    active_team: TeamName
    teams: Sequence[TeamName]


@dataclass
class SpawnInfo:
    """All of the values returned from the uid/gid system needed to spawn a user
    and fully identify them in the context of a notebook container and Ubuntu.
    """

    uid: Uid
    gid: Gid  # active group
    all_user_gids: list[Gid]  # all groups
    username: UserName
    groupname: GroupName  # active group
    etc_passwd: str
    etc_group: str


# -----------------------------------------------------------------------------------------


__all__ = [
    "StsciUuid",
    "UnicodeName",
    "StsciEzid",
    "TeamName",
    "RangedId",
    "Uid",
    "Gid",
    "SystemUid",
    "SystemGid",
    "UserUid",
    "UserGid",
    "GroupGid",
    "GroupAdminUid",
    "UserStatus",
    "UserType",
    "UbuntuName",
    "User",
    "UidGidInputs",
    "SpawnInfo",
]

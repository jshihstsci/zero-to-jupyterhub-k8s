"""Top level library module providing spawner a one-stop-shop i/f to uid/gid"""

import sys
import os
import subprocess
from pathlib import Path
import pwd
import grp
from unittest.mock import MagicMock

from uidgid import main
from uidgid.main import get_spawn_info, init_api
from uidgid.types import StsciUuid, StsciEzid, TeamName

import pytest

# ----------------------------------------------------------------------------

RUNNING_AS_ROOT = os.geteuid() == 0


def get_username():
    return pwd.getpwuid(os.geteuid())[0]


def get_groupname():
    return grp.getgrgid(os.getegid())[0]


# ----------------------------------------------------------------------------


def check_user(ezid, uid):
    user_store, group_store = main.UID_GID_API.users, main.UID_GID_API.groups
    user = user_store.get_user_info(ezid, id_type="ezid")
    group = group_store.get_group_info(user.username, id_type="groupname")
    assert user.ezid == ezid, f"Expected {repr(user)} to be ezid {ezid};  real user"
    assert user.uid == uid, f"Expected {repr(user)} to be uid {uid};  real user"
    assert group.gid == uid, f"Expected {repr(user)} to be group {uid};  personal group"
    main.UID_GID_API.check_home_dir(user.username, check_ownership=RUNNING_AS_ROOT)


def check_group(teamname, gid, membernames):  # members should be ezid
    user_store, group_store = main.UID_GID_API.users, main.UID_GID_API.groups
    group = group_store.get_group_info(teamname, id_type="teamname")
    user = user_store.get_user_info(group.gid, id_type="uid")
    assert (
        group.gid == gid
    ), f"Expected group gid for group {group.groupname} to be {gid};  real group"
    assert (
        user.uid == gid
    ), f"Expected group uid for user {user.username} to be {gid};  admin user"
    for member in membernames:
        username = user_store.get_user_info(member, id_type="ezid").username
        assert group_store.is_user_in_group(
            username, group.groupname
        ), f"Expected username {username} to be in {group.groupname}"
        main.UID_GID_API.check_teams_dir(check_ownership=RUNNING_AS_ROOT)
        main.UID_GID_API.check_group_dir(
            group.groupname, check_ownership=RUNNING_AS_ROOT
        )


def check_not_group(teamname, membernames):  # members should be usernames
    user_store, group_store = main.UID_GID_API.users, main.UID_GID_API.groups
    group = group_store.get_group_info(teamname, id_type="teamname")
    for member in membernames:
        username = user_store.get_user_info(member, id_type="teamname").username
        assert group_store.is_user_in_group(
            username, group.groupname
        ), f"Expected member {member} to be in group {group.groupname}"


def init():
    main.TEAMS_ROOT_DIR = Path("efs/teams")
    main.HOME_ROOT_DIR = Path("efs/users")
    main.UID_GID_ROOT_DIR = Path("efs/services/uidgid")
    main.BACKUP_ROOT_DIR = Path("efs/backups/uidgid")
    main.chown = MagicMock()
    done()
    main.UID_GID_ROOT_DIR.mkdir(parents=True, exist_ok=True)
    main.BACKUP_ROOT_DIR.mkdir(parents=True, exist_ok=True)
    init_api(reinit=True)


def done():
    subprocess.run("make clean-test".split(), capture_output=True, check=True)
    print("\n", file=sys.stderr)
    print("\n", file=sys.stdout)
    sys.stderr.flush()
    sys.stdout.flush()


# ----------------------------------------------------------------------------


def test_add_new_user_and_group():  # (setup_mocks):
    """Add a new user in two new groups."""
    init()
    info = get_spawn_info(
        "12345678-1234-1234-1234-123456789abc",
        "user_1",
        "team_2",
        ["team_1", "team_2"],
    )
    check_group("team_1", 60000, ["user_1"])
    check_group("team_2", 60001, ["user_1"])
    assert info.uid == 1001, "Expected user uid to be 1001;  real user"
    assert info.gid == 60001, "Expected user gid to be 60001;  real group"
    assert info.username == "user-1", "Expected username to be user_1;  real user"
    assert info.all_user_gids == [
        1001,
        60000,
        60001,
    ], "Expected all_user_gids to be [1001, 60000, 60001];  real user"
    done()


def test_add_existing_user_to_new_group():
    """Add an existing user to a new group."""
    init()
    info = get_spawn_info(
        "12345678-1234-1234-1234-123456789abc",
        "user_1",
        "team_2",
        ["team_1", "team_2"],
    )
    info = get_spawn_info(
        "12345678-1234-1234-1234-123456789abc",
        "user_1",
        "team_1",
        ["team_1", "team_2", "team_3"],
    )
    check_user("user_1", 1001)
    check_group("team_1", 60000, ["user_1"])
    check_group("team_2", 60001, ["user_1"])
    check_group("team_3", 60002, ["user_1"])
    assert info.uid == 1001, "Expected user uid to be 1001;  real user"
    assert info.gid == 60000, "Expected user gid to be 60001;  real group"
    assert info.all_user_gids == [
        1001,
        60000,
        60001,
        60002,
    ], "Expected all_user_gids to be [1001, 60000, 60001, 60002];  real user"
    done()


def test_add_existing_user_to_existing_group():
    """Add an existing user to an existing group created for/by a different user."""
    init()
    info = get_spawn_info(  # user_1 creates themselves but joins no teams
        "12345678-1234-1234-1234-123456789abd",
        "user_1",
        "user_1",
        [],
    )
    info = get_spawn_info(  # user_2 creates 2 teams + themselves
        "12345678-1234-1234-1234-123456789abc",
        "user_2",
        "team_2",
        ["team_1", "team_2"],
    )
    info = get_spawn_info(  # user_1 comes back and joins team_1
        "12345678-1234-1234-1234-123456789abd",
        "user_1",
        "team_1",
        ["team_1"],
    )
    check_user("user_1", 1001)
    check_user("user_2", 1002)
    check_group("team_1", 60000, ["user_2", "user_1"])
    check_group("team_2", 60001, ["user_2"])
    assert info.uid == 1001, "Expected user uid to be 1001;  real user"
    assert info.gid == 60000, "Expected user gid to be 60000;  real group"
    assert info.all_user_gids == [
        1001,
        60000,
    ], "Expected all_user_gids to be [1001, 60000];  real user"
    done()


def test_group_remove():
    """Add an existing user to a new group."""
    init()
    info = get_spawn_info(
        "12345678-1234-1234-1234-123456789abc",
        "user_1",
        "team_2",
        ["team_1", "team_2", "team_3"],
    )
    info = get_spawn_info(
        StsciUuid("12345678-1234-1234-1234-123456789abc"),
        StsciEzid("user_1"),
        TeamName("team_1"),
        [TeamName("team_1"), TeamName("team_4")],
    )
    check_user("user_1", 1001)
    check_group("team_1", 60000, ["user_1"])
    check_group("team_2", 60001, [])
    check_group("team_3", 60002, [])
    check_group("team_4", 60003, ["user_1"])
    assert info.uid == 1001, "Expected user uid to be 1001;  real user"
    assert (
        info.gid == 60000
    ), "Expected user gid to be 60001;  active group not personal group"
    done()


def test_everything_already_defined():
    init()
    info = get_spawn_info(
        "12345678-1234-1234-1234-123456789abc",
        "user_1",
        "team_2",
        ["team_1", "team_2"],
    )
    check_user("user_1", 1001)
    check_group("team_1", 60000, ["user_1"])
    check_group("team_2", 60001, ["user_1"])
    assert info.uid == 1001, "Expected user uid to be 1001;  real user"
    assert info.gid == 60001, "Expected user gid to be 60001;  real group"
    info = get_spawn_info(
        "12345678-1234-1234-1234-123456789abc",
        "user_1",
        "team_2",
        ["team_1", "team_2"],
    )
    check_user("user_1", 1001)
    check_group("team_1", 60000, ["user_1"])
    check_group("team_2", 60001, ["user_1"])
    assert info.uid == 1001, "Expected user uid to be 1001;  real user"
    assert info.gid == 60001, "Expected user gid to be 60001;  real group"
    done()


def test_bad_admin_group_active():
    init()
    get_spawn_info(
        "12345678-1234-1234-1234-123456789abc",
        "user_1",
        "team_2",
        ["team_1", "team_2"],
    )
    with pytest.raises(
        ValueError,
        match=r".*Active team team_2 not in user's teams \['team_1', 'team_3'\].*",
    ):
        get_spawn_info(
            "12345678-1234-1234-1234-123456789abc",
            "user_2",
            "team_2",
            ["team_1", "team_3"],
        )
    done()


def test_add_new_user_no_teams():
    """Add a new user in two new groups."""
    init()
    info = get_spawn_info(
        "12345678-1234-1234-1234-123456789abc",
        "user_1",
        "user_1",
        [],
    )
    check_user("user_1", 1001)
    assert info.uid == 1001, "Expected user uid to be 1001;  real user"
    assert info.gid == 1001, "Expected user gid to be 1001;  personal group"
    done()


def test_add_new_user_bogus_uuid():
    """Verify the lame pissinig non-hyphentated case which looks like trash works.."""
    init()
    info = get_spawn_info(
        "12345678123412341234123456789abc",
        "user_1",
        "user_1",
        [],
    )
    check_user("user_1", 1001)
    assert info.uid == 1001, "Expected user uid to be 1001;  real user"
    assert info.gid == 1001, "Expected user gid to be 1001;  personal group"
    done()


def test_add_new_user_typed_parameters():
    """Add a new user in two new groups."""
    init()
    info = get_spawn_info(
        StsciUuid("12345678-1234-1234-1234-123456789abc"),
        StsciEzid("user_1"),
        TeamName("user_1"),
        [],
    )
    check_user("user_1", 1001)
    assert info.uid == 1001, "Expected user uid to be 1001;  real user"
    assert info.gid == 1001, "Expected user gid to be 1001;  personal group"
    done()


def test_check_xxx_no_ownership():
    init()
    with pytest.raises(AssertionError):
        main.TEAMS_ROOT_DIR.mkdir(parents=True, exist_ok=True)
        main.UID_GID_API.check_teams_dir(check_ownership=True)
    with pytest.raises(AssertionError):
        (main.TEAMS_ROOT_DIR / "team-1").mkdir(parents=True, exist_ok=True)
        main.UID_GID_API.check_group_dir("team-1", check_ownership=True)
    with pytest.raises(AssertionError):
        (main.HOME_ROOT_DIR / "user-1").mkdir(parents=True, exist_ok=True)
        main.UID_GID_API.check_home_dir("user-1", check_ownership=True)
    done()


def test_backup_rosetta_tables(capsys):
    # First make sure we have some Rosetta tables.
    with capsys.disabled():
        test_add_new_user_and_group()
        init()
    # Then back them up and capture the event str
    main.UID_GID_API.backup_rosetta_using_log()
    captured = capsys.readouterr()
    main.UID_GID_API.locked_restore_rosetta_files(captured.out)
    done()


def test_names_must_be_mapped():  # (setup_mocks):
    """Add a new user in two new groups."""
    init()
    get_spawn_info(
        "087762a5-b48f-4915-a821-2158ab04babd",
        "jmatuskey",
        "437.Matuskey",
        [
            "437.Matuskey",
            "z1111.Bucklew",
            "z1112.Bucklew",
            "z951.Mutchler",
            "z993.Mutchler",
            "z50005.Murray",
        ],
    )
    # check_user("user_1", 1001)
    # check_group("team_1", 60000, ["user_1"])
    # check_group("team_2", 60001, ["user_1"])
    # assert info.uid == 1001, "Expected user uid to be 1001;  real user"
    # assert info.gid == 60001, "Expected user gid to be 60001;  real group"
    done()


def test_invalid_parameter_types():
    init()
    with pytest.raises(TypeError):
        get_spawn_info(
            123,
            "user_1",
            "team_1",
            ["team_1", "team_2"],
        )
    with pytest.raises(TypeError):
        get_spawn_info(
            "12345678-1234-1234-1234-123456789abc",
            123,
            "team_1",
            ["team_1", "team_2"],
        )
    with pytest.raises(TypeError):
        get_spawn_info(
            "12345678-1234-1234-1234-123456789abc",
            "user_1",
            123,
            ["team_1", "team_2"],
        )
    with pytest.raises(TypeError):
        get_spawn_info(
            "12345678-1234-1234-1234-123456789abc",
            "user_1",
            "team_1",
            [123, "team_2"],
        )
    done()


def test_invalid_uuid_format():
    init()
    with pytest.raises(ValueError):
        get_spawn_info(
            "invalid-uuid",
            "user_1",
            "team_1",
            ["team_1", "team_2"],
        )
    done()


def test_invalid_ezid_format():
    init()
    with pytest.raises(TypeError):
        get_spawn_info(
            "12345678-1234-1234-1234-123456789abc",
            1,
            "team_1",
            ["team_1", "team_2"],
        )
    done()


def test_invalid_team_name_format():
    init()
    with pytest.raises(TypeError):
        get_spawn_info(
            "12345678-1234-1234-1234-123456789abc",
            "user_1",
            1,
            ["team_1", "team_2"],
        )
    with pytest.raises(ValueError):
        get_spawn_info(
            "12345678-1234-1234-1234-123456789abc",
            "user_1",
            "team_1",
            ["invalid_team_name", "team_2"],
        )
    done()


def test_active_team_not_in_teams():
    init()
    with pytest.raises(ValueError):
        get_spawn_info(
            "12345678-1234-1234-1234-123456789abc",
            "user_1",
            "team_3",
            ["team_1", "team_2"],
        )
    done()

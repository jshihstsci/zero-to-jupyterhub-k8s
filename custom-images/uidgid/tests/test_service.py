"""Web client to get spawn info from uidgid service."""

from uidgid.client import cached_get_spawn_info as get_spawn_info


def test_add_new_user_and_group():  # (setup_mocks):
    """Add a new user in two new groups."""
    info = get_spawn_info(
        "12345678-1234-1234-1234-123456789abc",
        "user_1",
        "team_2",
        ["team_1", "team_2"],
    )
    assert info.uid == 1001, "Expected user uid to be 1001;  real user"
    assert info.gid == 60001, "Expected user gid to be 60001;  real group"
    assert info.username == "user-1", "Expected username to be user_1;  real user"
    assert info.all_user_gids == [
        1001,
        60000,
        60001,
    ], "Expected all_user_gids to be [1001, 60000, 60001];  real user"


def test_add_existing_user_to_new_group():
    """Add an existing user to a new group."""
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
    assert info.uid == 1001, "Expected user uid to be 1001;  real user"
    assert info.gid == 60000, "Expected user gid to be 60001;  real group"
    assert info.all_user_gids == [
        1001,
        60000,
        60001,
        60002,
    ], "Expected all_user_gids to be [1001, 60000, 60001, 60002];  real user"


def test_everything_already_defined():
    info = get_spawn_info(
        "12345678-1234-1234-1234-123456789abc",
        "user_1",
        "team_2",
        ["team_1", "team_2"],
    )
    assert info.uid == 1001, "Expected user uid to be 1001;  real user"
    assert info.gid == 60001, "Expected user gid to be 60001;  real group"
    info = get_spawn_info(
        "12345678-1234-1234-1234-123456789abc",
        "user_1",
        "team_2",
        ["team_1", "team_2"],
    )
    assert info.uid == 1001, "Expected user uid to be 1001;  real user"
    assert info.gid == 60001, "Expected user gid to be 60001;  real group"

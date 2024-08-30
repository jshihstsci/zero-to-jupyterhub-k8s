import pytest

from uidgid.types import (
    StsciUuid,
    UnicodeName,
    StsciEzid,
    TeamName,
    SystemUid,
    SystemGid,
    UserStatus,
    UbuntuName,
)


def test_valid_uuid():
    uuid = "12345678-1234-1234-1234-123456789abc"
    assert isinstance(StsciUuid(uuid), StsciUuid)


def test_invalid_uuid():
    with pytest.raises(ValueError):
        StsciUuid("invalid-uuid")


def test_invalid_type_uuid():
    with pytest.raises(TypeError):
        StsciUuid(1)


def test_valid_name_loose_unicode_identifier():
    name = "a" * 127
    assert isinstance(UnicodeName(name), UnicodeName)


def test_invalid_name_length_loose_unicode_identifier():
    with pytest.raises(ValueError):
        UnicodeName("a" * 128)


def test_invalid_type_loose_unicode_identifier():
    with pytest.raises(TypeError):
        UnicodeName(1)


def test_inheritance_stsci_ezid():
    name = "unique_identifier"
    assert isinstance(StsciEzid(name), UnicodeName)


def test_loose_constraints_stsci_ezid():
    StsciEzid("Jürgen Müller-Hartmann")
    StsciEzid("homer-the-man@gmail.com")


def test_invalid_length_stsci_ezid():
    with pytest.raises(ValueError):
        StsciEzid("a" * 128)


def test_inheritance_proper_team_name():
    name = "unique_identifier"
    assert isinstance(TeamName(name), UnicodeName)


def test_loose_constraints_proper_team_name():
    TeamName("Jürgen Müller Team")
    TeamName("red-team@gmail.com")


def test_invalid_length_proper_team_name():
    with pytest.raises(ValueError):
        TeamName("a" * 128)


def test_system_uid_within_range():
    assert isinstance(SystemUid(500), SystemUid)


def test_system_uid_out_of_range():
    with pytest.raises(ValueError):
        SystemUid(1000)  # Assuming this is outside the SystemUid range


def test_valid_status_user_status():
    assert UserStatus("active") == "active"


def test_invalid_status_user_status():
    with pytest.raises(AssertionError):
        UserStatus("invalid")


def test_valid_name_username():
    name = "valid-name"
    assert UbuntuName.is_valid(name)


def test_invalid_name_username():
    name = "Invalid_Name"
    assert not UbuntuName.is_valid(name)


def test_validate_range_id():
    with pytest.raises(TypeError):
        SystemUid.validate("foo")
    with pytest.raises(TypeError):
        SystemUid.validate(1.0)
    # Different classes of ID are comparable because they are all
    # related,  either the same "kind" (e.g. either uid or gid) or
    # else parallel ranges between different kinds (e.g. uid and gid).
    SystemUid.validate(SystemGid(500))


class TestStsciUuid:
    def test_valid_uuid_with_hyphens(self):
        uuid = "12345678-1234-1234-1234-123456789abc"
        assert isinstance(StsciUuid(uuid), StsciUuid)

    def test_valid_uuid_without_hyphens(self):
        uuid = "12345678123412341234123456789abc"
        assert isinstance(StsciUuid(uuid), StsciUuid)

    def test_uuid_with_leading_trailing_whitespace(self):
        uuid = "  12345678-1234-1234-1234-123456789abc  "
        assert isinstance(StsciUuid(uuid), StsciUuid)

    def test_uuid_with_mixed_case(self):
        uuid = "12345678-1234-1234-1234-123456789AbC"
        assert isinstance(StsciUuid(uuid), StsciUuid)

    def test_uuid_with_invalid_characters(self):
        with pytest.raises(ValueError):
            StsciUuid("invalid-uuid-with-chars")

    def test_uuid_with_invalid_length(self):
        with pytest.raises(ValueError):
            StsciUuid("12345678-1234-1234-1234-12345678")

    def test_uuid_with_empty_string(self):
        with pytest.raises(ValueError):
            StsciUuid("")

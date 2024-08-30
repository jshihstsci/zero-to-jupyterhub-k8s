import os
from unittest.mock import patch

import pytest

from uidgid.username import to_valid_username, make_unique, demo
from uidgid.types import UbuntuName


def test_unicode_to_ascii():
    username = "Jöhn_Döe"
    result = to_valid_username(username)
    assert all(
        c in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-"
        for c in result
    )


def test_drop_email_domain():
    username = "john.doe@example.com"
    result = to_valid_username(username)
    assert "@" not in result and "example.com" not in result


def test_replace_spaces_and_underscores():
    username = "john_doe doe"
    result = to_valid_username(username)
    assert result.count("_") == 0
    assert "-" in result


def test_length_restriction():
    UbuntuName.MAX_LEN = 32  # Assuming this is set somewhere in the code.
    username = "a" * 50  # Exceeds max length
    result = to_valid_username(username)
    assert len(result) <= UbuntuName.MAX_LEN


def test_make_unique():
    existing_names = ["user", "user-0", "user-1"]
    name = "user"
    result = make_unique(name, existing_names)
    assert result not in existing_names
    assert result == "user-2"


def test_invalid_characters_removed():
    username = "user!@#$%^&*()"
    result = to_valid_username(username)
    assert all(
        c in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-"
        for c in result
    )


def test_raise_error_for_invalid_generated_name():
    assert to_valid_username("Invalid_user_name_!@#$%^&*", []) == "invalid-user-name"
    assert to_valid_username("u-----", ["u"]) == "u-1"


def test_valid_chars():
    with pytest.raises(ValueError):
        to_valid_username("_____")


def test_invalid_name_generated():
    with patch("uidgid.username.make_unique") as mock_to_valid_username:
        mock_to_valid_username.return_value = "invalid-user_#@!"
        with pytest.raises(ValueError):
            demo()


def test_teamname():
    assert to_valid_username("123456.Abcdefg"), "u-123456-abcdefg"
    os.environ["DEPLOYMENT_NAME"] = "roman"
    assert to_valid_username("123456.Abcdefg", kind="group"), "rmn-123456-abcdefg"
    os.environ["DEPLOYMENT_NAME"] = "tike"
    assert to_valid_username("123456.Abcdefg", kind="group"), "tk-123456-abcdefg"
    os.environ["DEPLOYMENT_NAME"] = "jwebbinar"
    assert to_valid_username("123456.Abcdefg", kind="group"), "jwbnr-123456-abcdefg"
    os.environ["DEPLOYMENT_NAME"] = "jwst"
    assert to_valid_username("123456.Abcdefg", kind="group"), "jwst-123456-abcdefg"
    os.environ["DEPLOYMENT_NAME"] = "foolhardy"
    assert to_valid_username("123456.Abcdefg", kind="group"), "flhrdy-123456-abcdefg"


def test_demo():
    demo()

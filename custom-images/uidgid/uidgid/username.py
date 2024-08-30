"""Utility which maps upstream names with permissive formats onto UNIX viable names."""

import os
import re
from unidecode import unidecode

from uidgid.types import StsciEzid, UbuntuName


def to_valid_username(
    username: StsciEzid,
    existing_names: set[UbuntuName] | None = None,
    kind: str = "user",
) -> UbuntuName:
    """Squashes a unicode name with a weakly constrained characterset and
    arbitrary length into fewer than 32 ASCII characters starting with a letter
    and consisting only of upper and lower case letters, digits, and hyphens
    making the squashed name suitable for use by Ubuntu Linux to name users
    or groups.

    If the implied name begins with a digit or dash, the name is prefixed using
    the `prefix` argument which in the case of users may be "u-" but in the case
    of groups might be e.g. "roman-".
    """
    existing_names = existing_names or set()

    # Convert Unicode to nearest ASCII equivalent
    ascii_equivalent = unidecode(username)

    # drop email domain for privacy?
    ascii_equivalent = ascii_equivalent.split("@")[0]

    # convert spaces, underscores, and dots to dashes
    ascii_equivalent = re.sub(r"[\s_\.]", "-", ascii_equivalent.lower())

    # Keep only valid characters: lowercase letters, numbers, dash
    valid_chars = re.sub(r"[^a-z0-9-]", "", ascii_equivalent.lower())

    # Define a group name prefix used if first team char is not valid
    prefix = get_group_prefix() if kind != "user" else "u-"

    # Ensure the username does not start with a digit or dash, or add prefix
    if not re.match(r"^[a-z]", valid_chars):
        return to_valid_username(StsciEzid(prefix + valid_chars), existing_names)

    # Remove double dashes and trailing dashes
    while "--" in valid_chars:
        valid_chars = valid_chars.replace("--", "-")
    while valid_chars and valid_chars.endswith("-"):
        valid_chars = valid_chars[:-1]

    name = valid_chars[: UbuntuName.MAX_LEN]  # Restrict length / truncate

    name = make_unique(name, existing_names)

    if not UbuntuName.is_valid(name):
        raise ValueError(
            f"Generated name '{name}' from '{username}' is not valid for Ubuntu."
        )

    if name + "-" == prefix or name == prefix:
        raise ValueError(
            f"Generated name '{name}' from '{username}' is a degenerate form indicating other problems."
        )

    return UbuntuName(name)


def make_unique(
    candidate_name: str,
    existing_names: set[UbuntuName],
    max_length: int = UbuntuName.MAX_LEN,
) -> UbuntuName:
    """
    Returns a unique name that is not in the list of existing names and is no longer than the maximum length.
    If the candidate name is already unique and within the maximum length, it is returned as is.
    Otherwise, a decimal tail is added to the candidate name, and the name is truncated if necessary to fit within the maximum length.
    """
    unique_name = candidate_name
    counter = 1
    tail = None

    while unique_name in existing_names or len(unique_name) > max_length:
        # Truncate the name if it exceeds the maximum length
        if len(unique_name) > max_length:
            truncated_length = (
                max_length - len(str(counter)) - 1
            )  # Reserve space for the counter and a hyphen
            unique_name = candidate_name[:truncated_length]

        # If the name ends with the tail, remove it
        if tail and unique_name.endswith(tail):
            unique_name = unique_name[: -len(tail)]

        # Add a decimal tail to the name
        tail = f"-{counter}"
        unique_name = f"{unique_name}{tail}"
        counter += 1

    return UbuntuName(unique_name)


def get_group_prefix():
    """Returns the prefix for group names."""
    deployment = os.environ.get("DEPLOYMENT_NAME")

    # Default to deleting vowels if DEPLOYMENT_NAME is not mapped
    # to a predefined prefix below.
    default = "g" if deployment is None else re.sub(r"[aeiou]", "", deployment)

    return {
        "roman": "rmn",
        "tike": "tk",
        "jwebbinar": "jwb",
        "jwst": "jwst",
    }.get(deployment, default) + "-"


# -----------------------------------------------------------------------------------------


TEST_NAMES = [
    "Æon Flux_123!",
    "Marie-Claire Dupont",
    "João Silva",
    "Álvaro Espinoza",
    "Björn Svensson",
    "Inès Lefèvre",
    "Jürgen Müller-Hartmann",
    "Óscar Gutiérrez",
    "Anaïs Beauvais",
    "René Dubois-Lafont",
    "Lúcia dos Santos",
    "François Bertrand",
    "Erika Schmidt",
    "Gísli Magnússon",
    "Søren Kjær",
    "Zoë Richardson",
    "Finnur Jónsson",
    "Stéphane Girard",
    "Yvëtte D'Angelo",
    "Þór Björnsson",
    "Lars-Åke Lindström",
    "Raúl Navarro",
    "Elodie Rousseau",
    "İlker Yılmaz",
    "Máire Ní Chonchúir",
    "Úna Ó Súilleabháin",
    "homer-the-man@gmail.com",
    "doh@stsci.edu",
]


def demo():
    for name in TEST_NAMES:
        print(f"{name : <48}  {to_valid_username(name) : <32}")

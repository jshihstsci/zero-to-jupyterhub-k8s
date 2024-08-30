"""This module defines the client interface called by users of the UIDGID
service.  These client calls in turn perform HTTP requests to the server
which in turn calls the true UIDGID service code to perform UIDGID operations.
"""
import os
import requests
import functools

from uidgid.types import StsciUuid, StsciEzid, TeamName
from uidgid.types import SpawnInfo


SERVICE_URL = os.environ.get("UIDGID_CLIENT_URL", "http://127.0.0.1:5050")

LRU_CACHE_SIZE = 1024

# -------------------------------------------------------------------------------------


def check_alive(service_url=SERVICE_URL, timeout=30):
    response = requests.get(service_url + "/check-alive", timeout=timeout)
    assert response.status_code == 200
    return response.json()


def get_spawn_info(
    stsci_uuid: str,
    stsci_ezid: str,
    active_team: str,
    teams: list[str],
    service_url=SERVICE_URL,
    timeout=30,
) -> SpawnInfo:
    # Do input checks but keep simple objects for JSON serialization.
    StsciUuid(stsci_uuid)
    StsciEzid(stsci_ezid)
    TeamName(active_team)
    [TeamName(t) for t in teams]

    data = dict(
        stsci_uuid=stsci_uuid,
        stsci_ezid=stsci_ezid,
        active_team=active_team,
        teams=teams,
    )

    print("UIDGID get_spawn_info inputs: ", data)

    response = requests.post(
        service_url + "/get-spawn-info", json=data, timeout=timeout
    )

    if response.status_code == 200:
        info = SpawnInfo(**response.json())
        print("UIDGID get_spawn_info output: ", info)
        return info
    else:
        raise Exception(f"Failed to get spawn info: {response.text}")


# ---------------------------------------------------------------------


# First convert args to lru_cache-compatible,  then use lru_cache decorator
def cached_get_spawn_info(
    uuid, ezid, active_team, authorized_team_names, service_url=SERVICE_URL, timeout=30
):
    return lru_get_spawn_info(
        uuid,
        ezid,
        active_team,
        tuple([TeamName(t) for t in authorized_team_names]),  # lists are not hashable
        service_url,
        timeout,
    )


@functools.lru_cache(LRU_CACHE_SIZE)  # cache the last 32 different parameterizations+
def lru_get_spawn_info(
    uuid, ezid, active_team, authorized_team_names, service_url=SERVICE_URL, timeout=30
):
    return get_spawn_info(
        uuid, ezid, active_team, authorized_team_names, service_url, timeout
    )


def clear_cache():
    lru_get_spawn_info.cache_clear()

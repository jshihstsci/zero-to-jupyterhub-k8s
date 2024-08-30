import json
import datetime
from unittest.mock import patch
import traceback

import pytest

from uidgid.log import Log, get_pod_id, trim_time
from uidgid import log


@pytest.fixture
def mock_env(monkeypatch):
    monkeypatch.setenv("POD_NAME", "0")
    monkeypatch.setenv("ENVIRONMENT", "unknown-environment")
    monkeypatch.setenv("DEPLOYMENT_NAME", "unknown-deployment")
    monkeypatch.setenv("AWS_ACCOUNT_NAME", "unknown-account")


@pytest.fixture
def mock_now():
    with patch("uidgid.log.now") as mock_now:
        mock_now.return_value = "2024-05-04 12:00:00"
        yield


def test_get_pod_id():
    assert get_pod_id() == "0"


def test_now():
    now_time = log.now().split(".")[0]
    assert now_time == datetime.datetime.now().isoformat("T").split(".")[0]


def test_trim_time():
    assert trim_time(None) == "0001-01-01T01:01"
    assert trim_time("2023-05-01T12:34:56.789012") == "2023-05-01T12:34:56.789"


def test_log_dd_mode(capsys, mock_now, mock_env):
    logger = Log("uidgid")
    logger.set_dd_mode(True)
    logger.log("INFO", "test message")
    expected_output = {
        "status": "INFO",
        "subsystem": "uidgid",
        "pod_id": "0",
        "timestamp": log.now(),
        "message": "test message",
        "service": "unknown-deployment",
        "env": "dmd-unknown-environment",
        "aws-account-name": "unknown-account",
    }
    actual = json.loads(capsys.readouterr().out)
    assert actual == expected_output


def test_log_non_dd_mode(capsys, mock_now, mock_env):
    logger = Log("uidgid")
    logger.set_dd_mode(False)
    logger.log("INFO", "test message")
    expected_output = f"{log.now()} INFO : unknown-deployment : unknown-environment : uidgid : test message\n"
    captured = capsys.readouterr()
    assert captured.out == expected_output


def test_debug(capsys, mock_now, mock_env):
    logger = Log("test")
    logger.set_dd_mode(True)
    logger.debug_mode = True
    logger.debug("test message")
    expected_output = {
        "status": "DEBUG",
        "subsystem": "test",
        "pod_id": "0",
        "timestamp": log.now(),
        "message": "test message",
        "service": "unknown-deployment",
        "env": "dmd-unknown-environment",
        "aws-account-name": "unknown-account",
    }
    capsys.readouterr().out == expected_output


def test_exception(capsys, mock_now, mock_env):
    logger = Log("test")
    logger.set_dd_mode(True)
    try:
        raise ValueError("test exception")
    except ValueError as e:
        logger.exception(e, "test message")
        captured = capsys.readouterr()
        expected_output = {
            "status": "ERROR",
            "subsystem": "test",
            "pod_id": "0",
            "timestamp": log.now(),
            "message": "test message",
            "service": "unknown-deployment",
            "env": "dmd-unknown-environment",
            "aws-account-name": "unknown-account",
            "error.stack": traceback.format_exc(),
            "error.message": "test message",
            "error.kind": "ValueError",
        }
    actual = json.loads(captured.out)
    assert actual == expected_output

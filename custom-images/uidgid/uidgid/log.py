"""This module provides a Log class for logging to stdout in a simple way
with two special features:  Optioally the log format can be configfured as
DataDog compatible event messages instead of plain text.  The second feature
is that the log messages can be sent to the background in a thread which
offloads both message formatting work and any I/O blocking from the main
service thread enabling the service to respond faster and support bursts
of requests effectively.
"""

import os
import sys
import traceback
import datetime
import json

from uidgid.background import run_background

# ========================================================================================

NULL_TIME = "0001-01-01T01:01"


def get_pod_id():
    name = os.environ.get("POD_NAME") or "0"
    return "-".join(name.split("-")[-2:])


def now():
    return trim_time(datetime.datetime.now().isoformat("T"))


def trim_time(t):
    """Format times from JH in quota format by trimming subseconds and timezone."""
    return NULL_TIME if t is None else t[: t.index(".") + 4]


# ========================================================================================


class Log:
    def __init__(self, subsystem, dd_mode=False, debug_mode=False):
        self.dd_mode = dd_mode
        self.debug_mode = debug_mode
        self.subsystem = subsystem
        self.pod_id = get_pod_id()
        self.environment = os.environ.get("ENVIRONMENT", "unknown-environment").replace(
            "prod", "ops"
        )
        self.deployment = os.environ.get("DEPLOYMENT_NAME", "unknown-deployment")
        self.aws_account_name = os.environ.get("AWS_ACCOUNT_NAME", "unknown-account")

    def set_level(self, level):
        """If level is "DEBUG" then enable debug mode and output log.debug
        messages.   Otherwise mute log.debug messages."""
        old, Log.debug_mode = Log.debug_mode, level == "DEBUG"
        return old

    def set_dd_mode(self, events: bool = False):
        """When False output events as plain text.  When True output DataDog
        JSON event format.
        """
        old, self.dd_mode = self.dd_mode, events
        return old

    def log(self, kind, *args, **keys):
        if os.environ.get("SERVICE_LOGGING"):
            run_background(self._log, (kind, now()) + args, keys)
        else:
            self._log(kind, now(), *args, **keys)

    def _log(self, kind, timestamp, *args, **keys):
        d = dict(keys)
        d["status"] = kind
        d["subsystem"] = self.subsystem
        d["pod_id"] = self.pod_id
        d["timestamp"] = timestamp
        d["message"] = " ".join([str(arg) for arg in args])
        d["service"] = self.deployment  # e.g. roman
        d["env"] = "dmd-" + self.environment  # e.g. dev, test, ops
        d["aws-account-name"] = self.aws_account_name
        dd_mode = d.pop("dd_mode", self.dd_mode)
        if dd_mode:
            print(json.dumps(d))
        else:
            print(
                d["timestamp"],
                kind,
                ":",
                self.deployment,
                ":",
                self.environment,
                ":",
                self.subsystem,
                ":",
                d["message"],
            )
        sys.stdout.flush()
        return d

    def debug(self, *args, **keys):
        if self.debug_mode:
            return self.log("DEBUG", *args, **keys)

    def info(self, *args, **keys):
        return self.log("INFO", *args, **keys)

    def warning(self, *args, **keys):
        return self.log("WARN", *args, **keys)

    def error(self, *args, **keys):
        return self.log("ERROR", *args, **keys)

    def critical(self, *args, **keys):
        return self.log("CRITICAL", *args, **keys)

    def exception(self, exc, *args, **keys):
        old_dd, self.dd_mode = self.dd_mode, True
        keys = dict(keys)
        keys.update(
            {
                "error.stack": traceback.format_exc(),
                "error.message": " ".join([str(arg) for arg in args]),
                "error.kind": exc.__class__.__name__,
            }
        )
        result = self.error(*args, dd_mode=True, **keys)
        self.dd_mode = old_dd
        return result

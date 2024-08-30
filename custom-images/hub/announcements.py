"""This module defines a message/announcements service for the JupyterHub.  It
run a tornado web service that can be used to send messages to all users or a
particular user.
"""
import os
import sys
import asyncio
import argparse
import datetime
import json

import re
import uuid
import time
from functools import partial
from dataclasses import dataclass

from tornado import web

from jupyterhub.services.auth import HubOAuthenticated, HubOAuthCallbackHandler
from markupsafe import escape as safe_escape  # included in hub pip environment

# ----------------------------------------------------------------------


def now() -> str:
    """Return a string representation of the current time in ISO format."""
    return datetime.datetime.now().isoformat()


def wlog(*args) -> None:
    """Quick and dirty debug logger,  uncomment return to disable."""
    return  # logging is disabled because it is blocking and will stall tornado
    print(*args)
    sys.stdout.flush()


def dt_from_iso(iso: str) -> datetime.datetime:
    """Convert an ISO formatted string to a datetime object."""
    return datetime.datetime.fromisoformat(iso.split(".")[0])


def delta_from_spec(spec) -> datetime.timedelta:
    """Convert our string representation of a timedelta to a timedelta object.

    Specs are in the form of <days>-<hours>:<minutes>:<seconds>

    Returns a datetime.timedelta object.
    """
    days = int(spec.split("-")[0], 10) if "-" in spec else 0
    hms = spec.split("-")[1] if "-" in spec else spec
    hours, minutes, seconds = map(int, hms.split(":"))
    return datetime.timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds)


# ----------------------------------------------------------------------

MAX_ANNOUNCEMENT_JSON = 1024

LEVELS = ["debug", "info", "notice", "warning", "error", "critical"]
POPUP_LEVELS = ["notice", "warning", "error", "critical"]

TIMESTAMP_REGEX = r"^\d\d\d\d-\d\d-\d\dT\d\d:\d\d(:\d\d(.\d\d\d(\d\d\d)?)?)?$"
EXPIRES_REGEX = r"^\d+\-\d\d:\d\d:\d\d$"

SYSTEM_USERS = ["efs-quota", "announcement"]

MESSAGE_Q_LEN = 5


class ContractError(Exception):
    """Error indicating an interface contract violation."""

    def __init__(self, message):
        super().__init__(message)


# pytest hogs assert so better not to use it
def contract(condition, failure_message):
    """Check a contract condition, raise a ContractError exception if it is violated."""
    if not condition:
        raise ContractError(failure_message)


@dataclass
class Message:
    """Data associated with a single announcement message.  Validates.
    Web input and output parameter.
    """

    username: str
    timestamp: str
    expires: str
    level: str
    message: str

    def __init__(self, username, timestamp, expires, level, message):
        """Create a new message.  Validates input.  Web input and output parameter.""" ""
        contract(len(username) < 32, "username too long")
        contract(
            re.match(r"^[a-zA-Z0-9_@.-]+$", username), "invalid username characters"
        )
        self.username = safe_escape(username)

        timestamp = now() if timestamp is None else timestamp
        contract(re.match(TIMESTAMP_REGEX, timestamp), "invalid timestamp format")
        self.timestamp = safe_escape(timestamp)

        expires = "2-00:00:00" if expires is None else expires
        contract(
            re.match(EXPIRES_REGEX, expires),
            "Invalid expires time: should be: DAYS-HH:MM:SS",
        )
        self.expires = safe_escape(expires)

        contract(
            re.match(r"^" + r"|".join(LEVELS) + r"$", level),
            "invalid level value;  should be one of: " + ", ".join(LEVELS),
        )
        self.level = safe_escape(level)

        contract(len(message) < 1024, "message too long")
        self.message = safe_escape(message)

        wlog(repr(self))

    def to_simpl(self) -> dict:
        """Convert to simple types for JSON encoding."""
        return dict(
            username=self.username,
            timestamp=self.timestamp,
            expires=self.expires,
            level=self.level,
            message=self.message,
        )

    def popup(self) -> bool:
        """Return true if this message should popup based on its level."""
        return self.level in POPUP_LEVELS


@dataclass
class MessageBlock:
    """A titled list of accumulated messages for one user which is
    ideal for display in a single section of the announcement div.
    """

    title: str
    messages: list[Message]

    def popup(self) -> bool:
        """Return true if any message in the block is a popup."""
        return any(message.popup() for message in self.messages)

    def to_simpl(self) -> dict:
        """Convert to simple types for JSON encoding."""
        return dict(
            title=self.title,
            messages=[message.to_simpl() for message in self.messages],
        )


class Announcement:
    """Contains the information returned for a single GET from a user,
    essentially a list titled sections of messages to display.
    """

    def __init__(self, blocks: list[MessageBlock]) -> None:
        self.timestamp = (
            now()
        )  # makes repeat announcement look unique == no browser caching?
        self.blocks = blocks

    def popup(self) -> bool:
        """Return true if any block in the announcement requests popup."""
        return any(block.popup() for block in self.blocks)

    def to_simpl(self) -> dict:
        """Convert to simple types for JSON encoding."""
        return dict(
            popup=self.popup(),
            timestamp=self.timestamp,
            blocks=[block.to_simpl() for block in self.blocks],
        )


# ----------------------------------------------------------------------


class Announcements:
    """Global store for all announcements, system and user,  loaded and saved.

    The  "store" is a dictionary of lists of Message objects, keyed by username.
    """

    def __init__(self, savefile: str) -> None:
        self.savefile: str = savefile
        self.store: dict[str, list[Message]] = {}
        self.dirty = False
        self.load()

    def to_dict(self) -> dict:
        """Convert to a simple dictionary of lists of string-ified Message
        objects, keyed by username,  suitable for a generic encoding into
        JSON or YAML.

        Returns a serializable version of the message store.
        """
        return {
            username: [value.to_simpl() for value in values]
            for username, values in self.store.items()
        }

    def from_dict(self, d: dict) -> dict[str, list[Message]]:
        """Converts the serialized version of an old message store
        into a dictionary of lists of Message objects, keyed by username.
        """
        return {
            username: [Message(**value) for value in values]
            for username, values in d.items()
        }

    def load(self) -> None:
        """Load the message store from the savefile,  nominally as JSON.

        If the load fails start over with an empty store.
        """
        try:
            wlog(f"Loading {self.savefile}...")
            with open(self.savefile, "r", encoding="utf-8") as file:
                self.store = self.from_dict(json.load(file))
            self.dirty = False
        except Exception as exc:
            wlog(
                f"Loading {self.savefile} failed.  Clearing all. Exception: {repr(exc)}"
            )
            self.store = {}
            self.dirty = True

    def save(self) -> None:
        """Save the message store to the savefile,  nominally as JSON."""
        wlog(f"Saving {self.savefile}...")
        with open(self.savefile, "w+", encoding="utf-8") as file:
            json.dump(self.to_dict(), file, indent=4)
        wlog(f"Saved {self.savefile}.")
        self.dirty = False

    def clear(self, username: str, clear_regex: str = ".*") -> None:
        """Clear/delete all messages for a user matching a regex or all users
        if username is "all".
        """
        usernames = self.store.keys() if username == "all" else [username]
        for username in usernames:
            for msg in list(self.store.get(username, [])):
                if re.search(clear_regex, msg.message):
                    self.store[username].remove(msg)
                    self.dirty = True

    def put(self, username: str, message: Message) -> None:
        """Add a message to the store for a user,  rotating the queue if needed."""
        if username not in self.store:
            self.store[username] = []
        self.store[username].append(message)
        self.rotate(username)
        self.dirty = True

    def rotate(self, username: str, q_len: int = MESSAGE_Q_LEN) -> None:
        """Rotate the message queue for a user to a fixed length,  deleting
        the oldest messages first.
        """
        if len(self.store[username]) > q_len:
            self.store[username] = self.store[username][1:]  # drop oldest message
            self.dirty = True

    def remove_expired(self) -> None:
        """Remove all messages older than their individual expiration times
        from the store.
        """
        t_now = datetime.datetime.now()
        for messages in self.store.values():
            for msg in messages:
                timestamp = dt_from_iso(msg.timestamp)
                expires = delta_from_spec(msg.expires)
                if timestamp + expires <= t_now:
                    messages.remove(msg)
                    self.dirty = True

    def has_messages(self, username) -> bool:
        """Return true if the user has any messages in the store."""
        return username in self.store and len(self.store[username]) > 0

    def get_announcement(self, usernames: list[str]) -> Announcement:
        """Return an Announcement object for a list of usernames,  implicitly including
        system messages first if any are present.
        """

        wlog("self.store:", self.store)
        wlog("usernames:", usernames)
        if self.has_messages("system"):
            blocks = [MessageBlock("System Messages", self.store["system"])]
        else:
            blocks = []
        for username in usernames:
            if self.has_messages(username):
                blocks.append(
                    MessageBlock(f"Messages for {username}", self.store[username])
                )
        return Announcement(blocks)


# ----------------------------------------------------------------------

ANNOUNCEMENTS = Announcements("/services/announcements/messages.json")


class AnnouncementRequestHandler(HubOAuthenticated, web.RequestHandler):
    """Dynamically manage page announcements"""

    def prepare(self):
        wlog(self.request)

    def _check_admin_user(self):
        username = self.get_current_user()["name"]  # from token
        if username not in SYSTEM_USERS:
            raise web.HTTPError(404)

    @property
    def url_username(self):  # from URL from announce script
        """Return the username appended to the URL by the announcement client."""
        return self.request.uri.split("/")[-1]

    @web.authenticated  # but only accessible to the service user
    def post(self):
        """Update announcement"""
        self._check_admin_user()
        payload = self.request.body
        if len(payload) > MAX_ANNOUNCEMENT_JSON:
            raise web.HTTPError(
                status_code=400,
                log_message="Bad request: Announcement JSON message too long.",
            )
        doc = json.loads(payload)
        try:
            msg = Message(
                username=doc["username"],
                timestamp=doc.get("timestamp", None),
                expires=doc.get("expires", None),
                level=doc.get("level", "info"),
                message=doc["message"],
            )
        except ContractError as e:
            raise web.HTTPError(status_code=400, log_message=str(e))
        replace = doc.get("replace", None)
        if replace:
            ANNOUNCEMENTS.clear(msg.username, replace)
        ANNOUNCEMENTS.put(msg.username, msg)
        self.write_to_json(msg.to_simpl())

    @web.authenticated
    def get(self):
        """Retrieve announcement"""
        # From notebook or cmd line client API token
        username = self.get_current_user()["name"]
        # cmd line client can specify which user to pull
        if username in SYSTEM_USERS:
            username = self.url_username
        if username == "all":
            raise web.HTTPError(
                status_code=400,
                log_message="Bad request:  username==all is not supported for GET",
            )
        wlog("GET username:", username)
        announcement = ANNOUNCEMENTS.get_announcement([username])
        self.write_to_json(announcement.to_simpl())

    @web.authenticated
    def delete(self):
        """Clear announcement"""
        self._check_admin_user()
        ANNOUNCEMENTS.clear(self.url_username)
        self.write_to_json([self.url_username])

    def write_to_json(self, doc):
        """Write dictionary document as JSON"""
        self.set_header("Content-Type", "application/json; charset=UTF-8")
        s = json.dumps(doc)
        self.write(s)
        wlog(s)


# ----------------------------------------------------------------------


def persist_thread():
    """Periodically check to see if any messages should expire or the contents
    of ANNOUNCEMENTS have otherwise changed.   This function is blocking on
    sleep and a write to disk so it will stall whatever event loop it runs
    in.
    """
    while True:
        time.sleep(10)
        ANNOUNCEMENTS.remove_expired()
        if ANNOUNCEMENTS.dirty:
            ANNOUNCEMENTS.save()


async def call_blocking(func, *args, **keys):
    """Run the specified synchronous function in a background thread
    so that it doesn't stall the main thread during its blocks.
    """
    binding = partial(func, *args, **keys)
    binding.__doc__ = f"partial: {func.__doc__}"
    loop = asyncio.get_event_loop()
    return loop.run_in_executor(None, binding)


async def announce_persist():
    """Create a simple async function which can be called by gather()."""
    await call_blocking(persist_thread)


# ----------------------------------------------------------------------


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--api-prefix",
        "-a",
        default=os.environ.get("JUPYTERHUB_SERVICE_PREFIX", "/services/announcements/"),
        help="application API prefix",
    )
    parser.add_argument(
        "--port", "-p", default=8888, help="port for API to listen on", type=int
    )
    return parser.parse_args()


def create_application(api_prefix=r"/"):
    """Create the Tornado application mapping URLs to handlers."""
    wlog(f"Waiting for oauth_callback at: {api_prefix}oauth_callback/?.*")
    for key, value in os.environ.items():
        wlog(f"Env {key} = {value}")
    return web.Application(
        [
            (api_prefix, AnnouncementRequestHandler),
            (api_prefix + r"oauth_callback/?.*", HubOAuthCallbackHandler),
            (api_prefix + r"latest-v2/?.*", AnnouncementRequestHandler),
        ],
        cookie_secret=str(uuid.uuid4()).encode("utf-8"),
        # debug=True,
    )


async def announce_handler_main():
    """Main entry point for the announcement application."""
    args = parse_arguments()
    app = create_application(args.api_prefix)
    app.listen(args.port)
    shutdown = asyncio.Event()
    await shutdown.wait()


# ----------------------------------------------------------------------


async def main():
    """Start primary and background tasks."""
    await asyncio.gather(announce_handler_main(), announce_persist())


if __name__ == "__main__":
    asyncio.run(main())

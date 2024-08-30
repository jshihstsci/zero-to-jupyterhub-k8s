"""This module defines the Quart app which is the web server for the uid/gid
system.  The Quart app is used to serve the REST API which is used to interact
with the uid/gid system.  The Quart app is also used to implement the background
event loop which is used to run long running or blocking operations such as
saving a file or outputting log messages.

Defining the app here alone allows it to be imported without other entanglememts
from the uid/gid system which might otherwise cause circular imports.
"""
from quart import Quart

# -------------------------------------------------------------------------------------

app = Quart(__name__)

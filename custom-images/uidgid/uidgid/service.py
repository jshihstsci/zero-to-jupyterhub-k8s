"""This module defines Quart request handlers which implement the REST API."""
import os

from quart import request, jsonify

from uidgid.main import get_spawn_info, init_api

from uidgid.app import app

# -------------------------------------------------------------------------------------


@app.route("/check-alive", methods=["GET"])
async def check_alive():
    api = init_api(reinit=False)
    api.log.info("UIDGID is alive.")
    return jsonify("ok")


@app.route("/get-spawn-info", methods=["POST"])
async def handle_spawn_info_request():
    data = await request.get_json()
    spawn_info = get_spawn_info(
        data["stsci_uuid"], data["stsci_ezid"], data["active_team"], data["teams"]
    )
    return jsonify(spawn_info)


if __name__ == "__main__":
    app.run(debug=bool(os.environ.get("DEBUG_QUART", False)))

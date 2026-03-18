"""Phone microphone page."""

import flask_babel
from flask import render_template
from flask_smorest import Blueprint

from pikaraoke.lib.current_app import get_karaoke_instance, get_site_name

_ = flask_babel.gettext

mic_bp = Blueprint("mic", __name__)


@mic_bp.route("/mic")
def mic_page():
    """Phone-friendly microphone capture page."""
    k = get_karaoke_instance()
    site_name = get_site_name()

    return render_template(
        "mic.html",
        site_title=site_name,
        title=_("Mic"),
        preferred_mic_url=f"{k.url}/mic",
        secure_server_url=k.url if k.url.startswith("https://") else None,
    )

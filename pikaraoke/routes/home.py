"""Home page route."""

from urllib.parse import urlsplit

import flask_babel
from flask import render_template
from flask_smorest import Blueprint

from pikaraoke.lib.current_app import get_karaoke_instance, get_site_name, is_admin

_ = flask_babel.gettext


home_bp = Blueprint("home", __name__)


def _supports_secure_mic_capture(base_url: str) -> bool:
    """Return whether the shared URL already satisfies browser mic requirements."""
    parsed = urlsplit(base_url)
    return parsed.scheme == "https" or parsed.hostname in {"localhost", "127.0.0.1", "::1"}


@home_bp.route("/")
def home():
    """Home page with now playing info and controls."""
    k = get_karaoke_instance()
    site_name = get_site_name()
    return render_template(
        "home.html",
        site_title=site_name,
        title="Home",
        transpose_value=k.playback_controller.now_playing_transpose,
        admin=is_admin(),
        is_transpose_enabled=k.is_transpose_enabled,
        volume=k.volume,
        mic_requires_https=not _supports_secure_mic_capture(k.url),
        preferred_mic_url=f"{k.url}/mic",
    )

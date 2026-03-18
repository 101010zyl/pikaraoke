"""Tests for the phone mic route."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import werkzeug
from flask import Flask
from flask_babel import Babel

if not hasattr(werkzeug, "__version__"):
    werkzeug.__version__ = "3.0.0"

from pikaraoke.routes.mic import mic_bp


@pytest.fixture
def app():
    template_folder = Path(__file__).resolve().parents[2] / "pikaraoke" / "templates"
    test_app = Flask(__name__, template_folder=str(template_folder))
    Babel(test_app)
    test_app.add_url_rule("/", endpoint="home.home", view_func=lambda: "")
    test_app.add_url_rule("/queue", endpoint="queue.queue", view_func=lambda: "")
    test_app.add_url_rule("/search", endpoint="search.search", view_func=lambda: "")
    test_app.add_url_rule("/browse", endpoint="files.browse", view_func=lambda: "")
    test_app.add_url_rule("/info", endpoint="info.info", view_func=lambda: "")
    test_app.register_blueprint(mic_bp)
    return test_app


@pytest.fixture
def client(app):
    return app.test_client()


class TestMicRoute:
    """Verify the mic page renders the expected entrypoint."""

    @patch("pikaraoke.routes.mic.get_site_name", return_value="PiKaraoke")
    @patch("pikaraoke.routes.mic.get_karaoke_instance")
    def test_mic_page_renders(self, mock_get_instance, _mock_get_site_name, client):
        karaoke = MagicMock()
        karaoke.url = "https://karaoke.local:5555"
        mock_get_instance.return_value = karaoke

        response = client.get("/mic")

        assert response.status_code == 200
        body = response.get_data(as_text=True)
        assert "Phone Mic" in body
        assert "https://karaoke.local:5555/mic" in body
        assert 'secureServerUrl: "https://karaoke.local:5555"' in body

    @patch("pikaraoke.routes.mic.get_site_name", return_value="PiKaraoke")
    @patch("pikaraoke.routes.mic.get_karaoke_instance")
    def test_http_server_renders_without_secure_upgrade_url(
        self, mock_get_instance, _mock_get_site_name, client
    ):
        karaoke = MagicMock()
        karaoke.url = "http://192.168.1.50:5555"
        mock_get_instance.return_value = karaoke

        response = client.get("/mic")

        assert response.status_code == 200
        body = response.get_data(as_text=True)
        assert "secureServerUrl: null" in body

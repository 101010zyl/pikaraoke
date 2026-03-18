"""Unit tests for externally shared PiKaraoke URLs."""

from unittest.mock import patch


class _KaraokeUrlHarness:
    """Minimal harness for exercising Karaoke.get_url() in isolation."""

    from pikaraoke.karaoke import Karaoke

    get_url = Karaoke.get_url

    def __init__(self, *, url_scheme="http", prefer_hostname=False):
        self.is_raspberry_pi = False
        self.platform = "linux"
        self.port = 5555
        self.prefer_hostname = prefer_hostname
        self.url_override = None
        self.url_scheme = url_scheme
        self.ip = ""


class TestKaraokeUrl:
    """Verify generated URLs match the active transport."""

    @patch("pikaraoke.karaoke.get_ip", return_value="192.168.1.25")
    def test_get_url_uses_configured_scheme_for_ip_address(self, _mock_get_ip):
        harness = _KaraokeUrlHarness(url_scheme="https")

        assert harness.get_url() == "https://192.168.1.25:5555"

    @patch("pikaraoke.karaoke.get_ip", return_value="192.168.1.25")
    @patch("socket.getfqdn", return_value="karaoke.local")
    def test_get_url_prefers_hostname_when_enabled(self, _mock_fqdn, _mock_get_ip):
        harness = _KaraokeUrlHarness(url_scheme="https", prefer_hostname=True)

        assert harness.get_url() == "https://karaoke.local:5555"

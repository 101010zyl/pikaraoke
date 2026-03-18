"""Focused tests for microphone-related Socket.IO event flow."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from pikaraoke.lib.mic_manager import MicManager
from pikaraoke.routes import socket_events


class _FakeSocketIO:
    """Capture registered handlers and emitted events without a real server."""

    def __init__(self):
        self.handlers = {}
        self.emit = MagicMock()

    def on(self, event_name):
        def decorator(func):
            self.handlers[event_name] = func
            return func

        return decorator


def _invoke(fake_socketio: _FakeSocketIO, event_name: str, sid: str, payload=None) -> None:
    handler = fake_socketio.handlers[event_name]
    with patch("pikaraoke.routes.socket_events.request", SimpleNamespace(sid=sid)):
        if payload is None:
            handler()
        else:
            handler(payload)


def _emitted(fake_socketio: _FakeSocketIO, event_name: str) -> list:
    return [call for call in fake_socketio.emit.call_args_list if call.args[0] == event_name]


@pytest.fixture
def fake_socketio():
    original_session_manager = socket_events.session_manager
    socket_events.session_manager = MicManager()
    fake = _FakeSocketIO()
    socket_events.setup_socket_events(fake)
    yield fake
    socket_events.session_manager = original_session_manager


class TestMicSocketEvents:
    """Verify active mic lifecycle and splash handoff behavior."""

    def test_register_mic_replaces_previous_phone_session(self, fake_socketio):
        _invoke(fake_socketio, "register_mic", "mic-1")
        first_session_id = _emitted(fake_socketio, "mic_registered")[0].args[1]["sessionId"]

        fake_socketio.emit.reset_mock()
        _invoke(fake_socketio, "register_mic", "mic-2")

        replaced = _emitted(fake_socketio, "mic_replaced")
        registered = _emitted(fake_socketio, "mic_registered")
        mic_state = _emitted(fake_socketio, "mic_state")

        assert replaced[0].args[1]["sessionId"] == first_session_id
        assert replaced[0].kwargs["room"] == "mic-1"
        assert registered[0].kwargs["room"] == "mic-2"
        assert registered[0].args[1]["sessionId"] != first_session_id
        assert mic_state[0].args[1] == {
            "sessionId": registered[0].args[1]["sessionId"],
            "micConnected": True,
            "splashConnected": False,
            "connected": False,
        }

    def test_master_disconnect_reassigns_active_session_to_new_splash(self, fake_socketio):
        _invoke(fake_socketio, "register_splash", "splash-1")
        _invoke(fake_socketio, "register_splash", "splash-2")
        fake_socketio.emit.reset_mock()

        _invoke(fake_socketio, "register_mic", "mic-1")
        session_id = _emitted(fake_socketio, "mic_registered")[0].args[1]["sessionId"]

        fake_socketio.emit.reset_mock()
        _invoke(fake_socketio, "disconnect", "splash-1")

        splash_role = _emitted(fake_socketio, "splash_role")
        session_available = _emitted(fake_socketio, "mic_session_available")
        mic_state = _emitted(fake_socketio, "mic_state")

        assert splash_role[0].args == ("splash_role", "master")
        assert splash_role[0].kwargs["room"] == "splash-2"
        assert session_available[0].args[1]["sessionId"] == session_id
        assert session_available[0].kwargs["room"] == "splash-2"
        assert {call.kwargs["room"] for call in mic_state} == {"splash-2", "mic-1"}

    def test_webrtc_answer_marks_session_connected(self, fake_socketio):
        _invoke(fake_socketio, "register_splash", "splash-1")
        _invoke(fake_socketio, "register_mic", "mic-1")
        session_id = _emitted(fake_socketio, "mic_registered")[0].args[1]["sessionId"]

        fake_socketio.emit.reset_mock()
        _invoke(
            fake_socketio,
            "webrtc_offer",
            "splash-1",
            {"sessionId": session_id, "description": {"type": "offer", "sdp": "offer-sdp"}},
        )

        offer = _emitted(fake_socketio, "webrtc_offer")
        assert offer[0].kwargs["room"] == "mic-1"

        fake_socketio.emit.reset_mock()
        _invoke(
            fake_socketio,
            "webrtc_answer",
            "mic-1",
            {"sessionId": session_id, "description": {"type": "answer", "sdp": "answer-sdp"}},
        )

        assert socket_events.session_manager.active_session.connected is True

        answer = _emitted(fake_socketio, "webrtc_answer")
        mic_state = _emitted(fake_socketio, "mic_state")
        state_by_room = {call.kwargs["room"]: call.args[1] for call in mic_state}

        assert answer[0].kwargs["room"] == "splash-1"
        assert state_by_room["splash-1"]["connected"] is True
        assert state_by_room["mic-1"]["connected"] is True

"""Unit tests for phone mic session state."""

from pikaraoke.lib.mic_manager import MicManager


class TestMicManager:
    """Verify master splash and mic session lifecycle behavior."""

    def test_register_splash_assigns_master_then_slave(self):
        manager = MicManager()

        assert manager.register_splash("splash-1") == "master"
        assert manager.register_splash("splash-2") == "slave"
        assert manager.master_splash_id == "splash-1"

    def test_register_mic_replaces_previous_session(self):
        manager = MicManager()

        first_session, replaced = manager.register_mic("mic-1")
        second_session, replaced = manager.register_mic("mic-2")

        assert replaced == first_session
        assert manager.active_session == second_session
        assert manager.get_session_for_mic("mic-1") is None
        assert manager.get_session_for_mic("mic-2") == second_session

    def test_unregister_master_elects_new_master_and_detaches_session(self):
        manager = MicManager()
        manager.register_splash("splash-1")
        manager.register_splash("splash-2")
        session, _ = manager.register_mic("mic-1")
        manager.attach_splash(session.session_id, "splash-1")
        manager.mark_connected(session.session_id)

        new_master, detached_session = manager.unregister_splash("splash-1")

        assert new_master == "splash-2"
        assert detached_session == session
        assert detached_session.splash_sid is None
        assert detached_session.connected is False

    def test_clear_mic_only_removes_matching_owner(self):
        manager = MicManager()
        session, _ = manager.register_mic("mic-1")

        assert manager.clear_mic("other") is None
        assert manager.active_session == session

        removed = manager.clear_mic("mic-1")

        assert removed == session
        assert manager.active_session is None

    def test_mark_connected_returns_none_for_unknown_session(self):
        manager = MicManager()

        assert manager.mark_connected("missing") is None

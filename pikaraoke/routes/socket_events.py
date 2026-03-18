"""Socket.IO event handlers for PiKaraoke."""

import logging

from flask import request

from pikaraoke.lib.current_app import get_karaoke_instance
from pikaraoke.lib.mic_manager import MicManager

session_manager = MicManager()


def _mic_state_payload() -> dict[str, bool | str | None]:
    """Build the current mic connection snapshot for clients."""
    session = session_manager.active_session
    return {
        "sessionId": session.session_id if session else None,
        "micConnected": session is not None,
        "splashConnected": bool(session and session.splash_sid),
        "connected": bool(session and session.connected),
    }


def _emit_mic_state(socketio) -> None:
    """Push the current mic state to the active mic and master splash."""
    payload = _mic_state_payload()
    session = session_manager.active_session

    if session_manager.master_splash_id:
        socketio.emit("mic_state", payload, room=session_manager.master_splash_id)
    if session:
        socketio.emit("mic_state", payload, room=session.mic_sid)


def setup_socket_events(socketio):
    """Register Socket.IO event handlers.

    Args:
        socketio: The SocketIO instance.
    """

    @socketio.on("end_song")
    def end_song(reason: str) -> None:
        """Handle end_song WebSocket event from client.

        Args:
            reason: Reason for ending the song (e.g., 'complete', 'error').
        """
        k = get_karaoke_instance()
        k.playback_controller.end_song(reason)

    @socketio.on("start_song")
    def start_song() -> None:
        """Handle start_song WebSocket event when playback begins."""
        k = get_karaoke_instance()
        k.playback_controller.start_song()

    @socketio.on("clear_notification")
    def clear_notification() -> None:
        """Handle clear_notification WebSocket event to dismiss notifications."""
        k = get_karaoke_instance()
        k.reset_now_playing_notification()

    @socketio.on("register_splash")
    def register_splash() -> None:
        """Handle splash screen registration and assign master/slave roles."""
        sid = request.sid
        role = session_manager.register_splash(sid)
        logging.info(f"Splash screen registered: {sid}")
        socketio.emit("splash_role", role, room=sid)
        logging.info(f"{role.title()} splash screens assigned: {sid}")

        if role == "master" and session_manager.active_session:
            session = session_manager.active_session
            socketio.emit(
                "mic_session_available",
                {"sessionId": session.session_id},
                room=sid,
            )
        _emit_mic_state(socketio)

    @socketio.on("register_mic")
    def register_mic() -> None:
        """Register a phone browser as the active microphone source."""
        sid = request.sid
        session, replaced_session = session_manager.register_mic(sid)
        logging.info(f"Mic registered: {sid} ({session.session_id})")

        if replaced_session:
            socketio.emit(
                "mic_replaced",
                {"sessionId": replaced_session.session_id},
                room=replaced_session.mic_sid,
            )

        socketio.emit(
            "mic_registered",
            {"sessionId": session.session_id},
            room=sid,
        )

        if session_manager.master_splash_id:
            socketio.emit(
                "mic_session_available",
                {"sessionId": session.session_id},
                room=session_manager.master_splash_id,
            )
        _emit_mic_state(socketio)

    @socketio.on("disconnect_mic")
    def disconnect_mic() -> None:
        """Explicitly end the active microphone session."""
        sid = request.sid
        session = session_manager.clear_mic(sid)
        if session:
            logging.info(f"Mic disconnected: {sid}")
            _emit_mic_state(socketio)

    @socketio.on("webrtc_offer")
    def webrtc_offer(payload: dict) -> None:
        """Relay the splash screen's WebRTC offer to the active phone mic."""
        sid = request.sid
        session_id = payload.get("sessionId")
        description = payload.get("description")

        if sid != session_manager.master_splash_id or not session_id or not description:
            return

        session = session_manager.attach_splash(session_id, sid)
        if not session:
            return

        socketio.emit(
            "webrtc_offer",
            {"sessionId": session.session_id, "description": description},
            room=session.mic_sid,
        )
        _emit_mic_state(socketio)

    @socketio.on("webrtc_answer")
    def webrtc_answer(payload: dict) -> None:
        """Relay the phone mic's WebRTC answer back to the splash screen."""
        sid = request.sid
        session_id = payload.get("sessionId")
        description = payload.get("description")
        session = session_manager.get_session(session_id) if session_id else None

        if not session or sid != session.mic_sid or not description or not session.splash_sid:
            return

        session_manager.mark_connected(session_id)
        socketio.emit(
            "webrtc_answer",
            {"sessionId": session.session_id, "description": description},
            room=session.splash_sid,
        )
        _emit_mic_state(socketio)

    @socketio.on("webrtc_ice_candidate")
    def webrtc_ice_candidate(payload: dict) -> None:
        """Relay ICE candidates between the splash screen and phone mic."""
        sid = request.sid
        session_id = payload.get("sessionId")
        candidate = payload.get("candidate")
        session = session_manager.get_session(session_id) if session_id else None

        if not session or not candidate:
            return

        target_sid = None
        if sid == session.mic_sid:
            target_sid = session.splash_sid
        elif sid == session.splash_sid or sid == session_manager.master_splash_id:
            target_sid = session.mic_sid

        if target_sid:
            socketio.emit(
                "webrtc_ice_candidate",
                {"sessionId": session.session_id, "candidate": candidate},
                room=target_sid,
            )

    @socketio.on("playback_position")
    def handle_playback_position(position: float) -> None:
        """Handle playback_position WebSocket event from the master splash screen.

        Args:
            position: Current playback position in seconds.
        """
        sid = request.sid
        if sid == session_manager.master_splash_id:
            k = get_karaoke_instance()
            k.playback_controller.now_playing_position = position
            # Broadcast position to all other splash screens (slaves)
            socketio.emit("playback_position", position, include_self=False)

    @socketio.on("disconnect")
    def handle_disconnect() -> None:
        """Handle Socket.IO client disconnection and manage splash role handover."""
        sid = request.sid
        if sid in session_manager.splash_connections:
            logging.info(f"Splash screen disconnected: {sid}")
            new_master, session = session_manager.unregister_splash(sid)
            if new_master:
                logging.info("Master splash disconnected, electing new master")
                socketio.emit("splash_role", "master", room=new_master)
                logging.info(f"New master splash elected: {new_master}")
                if session:
                    socketio.emit(
                        "mic_session_available",
                        {"sessionId": session.session_id},
                        room=new_master,
                    )
            _emit_mic_state(socketio)
            return

        session = session_manager.clear_mic(sid)
        if session:
            logging.info(f"Mic socket disconnected: {sid}")
            _emit_mic_state(socketio)

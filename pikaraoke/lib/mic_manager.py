"""Session state for browser-based microphone streaming."""

import secrets
from dataclasses import dataclass


@dataclass
class MicSession:
    """Represents the active phone microphone session."""

    session_id: str
    mic_sid: str
    splash_sid: str | None = None
    connected: bool = False


class MicManager:
    """Tracks master splash ownership and a single active mic session."""

    def __init__(self) -> None:
        self.splash_connections: set[str] = set()
        self.master_splash_id: str | None = None
        self.active_session: MicSession | None = None
        self._mic_sid_to_session_id: dict[str, str] = {}

    def register_splash(self, sid: str) -> str:
        """Register a splash connection and return its assigned role."""
        self.splash_connections.add(sid)
        if self.master_splash_id is None:
            self.master_splash_id = sid
            return "master"
        return "slave"

    def unregister_splash(self, sid: str) -> tuple[str | None, MicSession | None]:
        """Remove a splash connection and elect a new master if needed."""
        self.splash_connections.discard(sid)

        session = self.active_session
        if session and session.splash_sid == sid:
            session.splash_sid = None
            session.connected = False

        new_master = None
        if sid == self.master_splash_id:
            self.master_splash_id = None
            if self.splash_connections:
                new_master = next(iter(self.splash_connections))
                self.master_splash_id = new_master

        return new_master, session

    def register_mic(self, sid: str) -> tuple[MicSession, MicSession | None]:
        """Create a new active mic session, replacing any previous one."""
        replaced_session = self.active_session
        if replaced_session is not None:
            self._mic_sid_to_session_id.pop(replaced_session.mic_sid, None)

        session = MicSession(session_id=secrets.token_urlsafe(8), mic_sid=sid)
        self.active_session = session
        self._mic_sid_to_session_id[sid] = session.session_id
        return session, replaced_session

    def clear_mic(self, sid: str) -> MicSession | None:
        """Remove the active session if it belongs to the given mic socket."""
        if not self.active_session or self.active_session.mic_sid != sid:
            return None
        session = self.active_session
        self._mic_sid_to_session_id.pop(sid, None)
        self.active_session = None
        return session

    def get_session(self, session_id: str) -> MicSession | None:
        """Return the active session if the ID matches."""
        if self.active_session and self.active_session.session_id == session_id:
            return self.active_session
        return None

    def get_session_for_mic(self, sid: str) -> MicSession | None:
        """Return the active session owned by the given mic socket."""
        session_id = self._mic_sid_to_session_id.get(sid)
        if not session_id:
            return None
        return self.get_session(session_id)

    def attach_splash(self, session_id: str, splash_sid: str) -> MicSession | None:
        """Attach the current master splash to the active mic session."""
        session = self.get_session(session_id)
        if not session:
            return None
        session.splash_sid = splash_sid
        session.connected = False
        return session

    def mark_connected(self, session_id: str) -> MicSession | None:
        """Mark the active session as fully connected."""
        session = self.get_session(session_id)
        if not session:
            return None
        session.connected = True
        return session

import time
from dataclasses import dataclass


@dataclass
class OAuthStateEntry:
    code_verifier: str
    created_at: float


class OAuthStateStore:
    def __init__(self, ttl_sec: int = 600) -> None:
        self.ttl_sec = ttl_sec
        self._store: dict[str, OAuthStateEntry] = {}

    def _cleanup(self) -> None:
        now = time.time()
        expired = [state for state, entry in self._store.items() if now - entry.created_at > self.ttl_sec]
        for state in expired:
            self._store.pop(state, None)

    def put(self, state: str, code_verifier: str) -> None:
        self._cleanup()
        self._store[state] = OAuthStateEntry(code_verifier=code_verifier, created_at=time.time())

    def pop_valid(self, state: str) -> str | None:
        self._cleanup()
        entry = self._store.pop(state, None)
        if not entry:
            return None
        if time.time() - entry.created_at > self.ttl_sec:
            return None
        return entry.code_verifier

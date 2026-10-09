import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Config:
    data_dir: Path = field(default_factory=lambda: Path(os.environ.get("ULTRON_DATA_DIR") or
        Path(os.environ.get("LOCALAPPDATA", str(Path.home() / ".local/share"))) / "ULTRON"))
    token: str = field(default_factory=lambda: os.environ.get("ULTRON_SESSION_TOKEN") or secrets.token_urlsafe(32))
    port: int = field(default_factory=lambda: int(os.environ.get("ULTRON_PORT", "8765")))
    ollama_url: str = field(default_factory=lambda: os.environ.get("ULTRON_OLLAMA_URL", "http://127.0.0.1:11434"))
    ollama_model: str = field(default_factory=lambda: os.environ.get("ULTRON_OLLAMA_MODEL", "qwen3:4b"))
    parent_pid: int | None = field(default_factory=lambda: int(os.environ["ULTRON_PARENT_PID"]) if os.environ.get("ULTRON_PARENT_PID") else None)


class Vault:
    """OS credential store. Never fall back to plaintext files."""
    def get(self, name: str) -> str | None:
        injected = os.environ.get("ULTRON_" + name.upper())
        if injected:
            return injected
        try:
            import keyring
            return keyring.get_password("ULTRON", name)
        except Exception:
            return None

    def put(self, name: str, value: str) -> None:
        import keyring
        backend = keyring.get_keyring()
        if backend.priority <= 0 or "plaintext" in type(backend).__module__.lower():
            raise ValueError("Secure OS credential storage is unavailable; configure a supported keyring.")
        keyring.set_password("ULTRON", name, value)

    def delete(self, name: str) -> None:
        import keyring
        try:
            keyring.delete_password("ULTRON", name)
        except keyring.errors.PasswordDeleteError:
            pass

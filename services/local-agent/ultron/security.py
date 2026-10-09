import ipaddress
from pathlib import Path
from urllib.parse import urlsplit


def approved_path(value: str, roots: list[str], must_exist=False) -> Path:
    path = Path(value).expanduser().resolve(strict=must_exist)
    if not roots or not any(path.is_relative_to(Path(root).expanduser().resolve()) for root in roots):
        raise ValueError("Path is outside approved folders. Add a specific folder in Settings.")
    if any(part.lower() in {".git", ".aws", ".ssh", ".codex"} for part in path.parts):
        raise ValueError("Credential and Git metadata directories are protected")
    return path


def https_url(value: str) -> str:
    url = urlsplit(value)
    if url.scheme != "https" or not url.hostname or url.username or url.password or url.port not in (None, 443):
        raise ValueError("Use an HTTPS URL without embedded credentials or a custom port")
    host = url.hostname.lower()
    if host in {"localhost", "metadata.google.internal"} or host.endswith((".local", ".internal")):
        raise ValueError("Private destinations are not allowed")
    try:
        if not ipaddress.ip_address(host).is_global:
            raise ValueError("Private destinations are not allowed")
    except ValueError as exc:
        if "Private destinations" in str(exc):
            raise
    return value


def loopback_url(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"} or parsed.username:
        raise ValueError("Ollama must use a local loopback HTTP endpoint")
    return value.rstrip("/")

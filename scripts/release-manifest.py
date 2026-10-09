"""Generate release checksums. Hashes need a trusted delivery channel."""
import hashlib
import json
from pathlib import Path

release = Path(__file__).resolve().parents[1] / "apps/desktop/release"
files = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in release.glob("*.exe")}
if not files:
    raise SystemExit("No Windows executables found; build them first")
(release / "SHA256SUMS.json").write_text(json.dumps(files, indent=2), encoding="utf-8")
print(f"Checksums generated for {len(files)} executables")

"""Build the Windows backend. Does not install or deploy a release."""
import os
import subprocess
import sys
from pathlib import Path

if os.name != "nt":
    raise SystemExit("Build the Windows agent on Windows; cross-compilation is unsupported.")
root = Path(__file__).resolve().parents[1]
command = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir", "--name", "ultron-agent",
           "--distpath", str(root / "build/agent"), "--workpath", str(root / "build/pyinstaller"),
           "--specpath", str(root / "build"), "--paths", str(root / "services/local-agent")]
for package in ["ultron", "piper", "faster_whisper", "ctranslate2", "onnxruntime", "sounddevice", "playwright", "openwakeword", "googleapiclient", "keyring.backends", "mss", "pycaw"]:
    command += ["--collect-all", package]
command += [str(root / "scripts/agent-entry.py")]
subprocess.run(command, cwd=root, check=True)

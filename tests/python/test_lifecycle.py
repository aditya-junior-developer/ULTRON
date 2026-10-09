import os
import socket
import subprocess
import sys
import time

import httpx


def test_desktop_agent_exits_when_parent_is_gone(tmp_path):
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    process = subprocess.Popen([sys.executable, '-m', 'ultron', '--port', str(port)],
        env=os.environ | {'ULTRON_PARENT_PID':'99999999', 'ULTRON_DATA_DIR':str(tmp_path), 'ULTRON_SESSION_TOKEN':'lifecycle-test-only'},
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        healthy = False
        with httpx.Client(trust_env=False, timeout=0.3) as client:
            for _ in range(40):
                if process.poll() is not None:
                    break
                try:
                    healthy = client.get(f'http://127.0.0.1:{port}/health').status_code == 200
                    if healthy:
                        break
                except httpx.HTTPError:
                    pass
                time.sleep(0.05)
        assert healthy, 'Agent never reached its real health endpoint'
        assert process.wait(timeout=10) == 0, 'Parent-loss shutdown did not finish cleanly'
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()

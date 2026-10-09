"""Start portable development services in this cloud workspace, without exposing tokens."""
import json
import os
import secrets
import signal
import subprocess
import sys
import time
from pathlib import Path

import httpx
import psutil

root = Path(__file__).resolve().parents[1]
runtime = Path(os.environ.get('ULTRON_RUNTIME_DIR', '/workspace/ultron-runtime'))
runtime.mkdir(parents=True, exist_ok=True)
state_file = runtime / 'session.json'


def stop(state):
    for name in ('agent_pid', 'web_pid'):
        try:
            process = psutil.Process(state[name])
            if process.status() == psutil.STATUS_ZOMBIE:
                continue
            command = ' '.join(process.cmdline())
            expected = '-m ultron' if name == 'agent_pid' else 'vite/bin/vite.js'
            if expected not in command:
                raise ValueError('PID belongs to another process; refusing to stop it')
            for child in process.children(recursive=True):
                child.terminate()
            process.terminate()
            for _ in range(100):
                if not process.is_running() or process.status() == psutil.STATUS_ZOMBIE:
                    break
                time.sleep(0.1)
            else:
                process.kill()
        except (psutil.NoSuchProcess, psutil.ZombieProcess, ProcessLookupError):
            pass


if '--stop' in sys.argv:
    if state_file.exists():
        stop(json.loads(state_file.read_text()))
        state_file.unlink()
    print('Development services stopped')
    raise SystemExit(0)

if state_file.exists():
    existing = json.loads(state_file.read_text())
    try:
        with httpx.Client(trust_env=False, timeout=3) as client:
            response = client.get(existing['base']+'/settings', headers={'Authorization':'Bearer '+existing['token']})
            if response.status_code == 200:
                print('Existing authenticated local agent is ready; session metadata stays in the private runtime file')
                raise SystemExit(0)
    except httpx.HTTPError:
        pass
    stop(existing)
    state_file.unlink()

token = secrets.token_urlsafe(32)
agent_log = open(runtime / 'agent.log', 'a')
web_log = open(runtime / 'web.log', 'a')
agent = subprocess.Popen([sys.executable, '-m', 'ultron', '--port', '8765'], cwd=root,
    env=os.environ | {'ULTRON_SESSION_TOKEN':token, 'ULTRON_DATA_DIR':str(runtime / 'data')},
    stdout=subprocess.DEVNULL, stderr=agent_log, start_new_session=True)
web = subprocess.Popen(['node', str(root / 'node_modules/vite/bin/vite.js'), '--host', '127.0.0.1', '--port', '5173', '--strictPort'],
    cwd=root / 'apps/web', stdout=web_log, stderr=web_log, start_new_session=True)
state = {'base':'http://127.0.0.1:8765', 'token':token, 'agent_pid':agent.pid, 'web_pid':web.pid}
try:
    with httpx.Client(trust_env=False, timeout=2) as client:
        for _ in range(100):
            if agent.poll() is not None or web.poll() is not None:
                raise RuntimeError('A development service exited; inspect its runtime log')
            try:
                response = client.get(state['base']+'/settings', headers={'Authorization':'Bearer '+token})
                if response.status_code == 200 and client.get('http://127.0.0.1:5173').status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(0.1)
        else:
            raise RuntimeError('Development services did not become ready')
    fd = os.open(state_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as output:
        json.dump(state, output)
    print('Authenticated API and web development services verified. Private runtime session: '+str(state_file))
except BaseException:
    for process in (agent, web):
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
    raise
finally:
    agent_log.close()
    web_log.close()

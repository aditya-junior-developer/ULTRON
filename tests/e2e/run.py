"""Real browser/API workflow check; does not call AI, Google or deployed services."""
import json
import os
import secrets
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx
from playwright.sync_api import sync_playwright, expect

root = Path(__file__).resolve().parents[2]


def port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


api_port = port()
token = secrets.token_urlsafe(32)
with tempfile.TemporaryDirectory(prefix='ultron-e2e-') as directory:
    data = Path(directory)
    project = data / 'project'
    project.mkdir()
    note = project / 'notes.txt'
    note.write_text('original', encoding='utf-8')
    env = os.environ | {'ULTRON_SESSION_TOKEN': token, 'ULTRON_DATA_DIR': str(data / 'agent')}
    agent_log = open(data / 'agent-errors.log', 'w+')
    web_log = open(data / 'web.log', 'w+')
    agent = subprocess.Popen([sys.executable, '-m', 'ultron', '--port', str(api_port)], cwd=root,
        env=env, stdout=subprocess.DEVNULL, stderr=agent_log, start_new_session=os.name != 'nt')
    npm = 'npm.cmd' if os.name == 'nt' else 'npm'
    web = subprocess.Popen([npm, 'run', 'dev', '-w', '@ultron/web', '--', '--port', '5173', '--strictPort'], cwd=root,
        stdout=web_log, stderr=web_log, start_new_session=os.name != 'nt')
    errors = []
    try:
        base = f'http://127.0.0.1:{api_port}'
        with httpx.Client(headers={'Authorization': 'Bearer ' + token}, trust_env=False) as client:
            for _ in range(100):
                try:
                    if client.get(base+'/health').status_code == 200 and client.get('http://127.0.0.1:5173').status_code == 200:
                        break
                except httpx.HTTPError:
                    pass
                time.sleep(0.1)
            else:
                agent_log.seek(0)
                web_log.seek(0)
                raise AssertionError('Required services did not become ready: agent=' + str(agent.poll()) +
                    ' web=' + str(web.poll()) + '\n' + agent_log.read()[-2000:] + '\n' + web_log.read()[-2000:])
            response = client.patch(base+'/settings', json={'approved_roots': [str(project)]})
            response.raise_for_status()
        with sync_playwright() as p:
            executable = os.environ.get('ULTRON_TEST_BROWSER') or ('/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None)
            browser = p.chromium.launch(headless=True, executable_path=executable, args=['--no-sandbox'] if os.name != 'nt' else [])
            page = browser.new_page(viewport={'width': 1440, 'height': 1000})
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto('http://127.0.0.1:5173')
            page.get_by_label('Agent address').fill(base)
            page.get_by_label('Local session token').fill(token)
            page.get_by_role('button', name='Connect', exact=True).click()
            expect(page.get_by_role('heading', name='What shall we do today?')).to_be_visible()
            page.get_by_role('button', name='Memory', exact=True).click()
            page.get_by_label('Add a memory').fill('Use Hindi for personal reminders')
            page.get_by_role('button', name='Remember', exact=True).click()
            expect(page.get_by_role('paragraph').filter(has_text='Use Hindi for personal reminders')).to_be_visible()
            page.get_by_role('button', name='Task monitor', exact=True).click()
            expect(page.get_by_role('heading', name='Every action, accounted for.')).to_be_visible()
            page.get_by_role('combobox').select_option('write_file')
            page.get_by_label('Arguments (JSON)').fill(json.dumps({'path': str(note), 'content': 'approved edit'}))
            page.get_by_role('button', name='Create task', exact=True).click()
            approve = page.get_by_role('button', name='Approve this action', exact=True)
            expect(approve).to_be_visible()
            assert note.read_text() == 'original', 'File changed before approval'
            approve.click()
            expect(page.get_by_text('completed', exact=True)).to_be_visible(timeout=15000)
            assert note.read_text() == 'approved edit', 'Approved write did not execute'
            page.get_by_role('button', name='Assistant', exact=True).click()
            artifacts = root / 'artifacts'
            artifacts.mkdir(exist_ok=True)
            page.screenshot(path=str(artifacts / 'desktop.png'), full_page=True)
            page.set_viewport_size({'width': 390, 'height': 844})
            expect(page.get_by_role('heading', name='What shall we do today?')).to_be_visible()
            assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), 'Mobile horizontal overflow'
            page.screenshot(path=str(artifacts / 'mobile.png'), full_page=True)
            page.get_by_role('button', name='Stop all', exact=True).click()
            with httpx.Client(trust_env=False, headers={'Authorization':'Bearer '+token}) as client:
                assert client.get(base+'/settings').json()['tool_execution'] is False
            assert not errors, errors
            browser.close()
        print('Browser workflow PASSED: authenticated connection, memory persistence, approval-gated snapshot edit, mobile layout, emergency stop; no page errors')
    finally:
        if os.name != 'nt':
            import signal
            for process in (agent, web):
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGTERM)
        else:
            for process in (agent, web):
                if process.poll() is None:
                    subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], capture_output=True)
        agent.wait(timeout=10)
        web.wait(timeout=10)
        agent_log.close()
        web_log.close()

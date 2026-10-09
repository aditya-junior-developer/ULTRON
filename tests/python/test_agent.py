import asyncio
import time

import httpx
import pytest

from ultron.actions import Actions, TaskEngine
from ultron.ai import AI, Reply
from ultron.config import Config
from ultron.google import Google
from ultron.security import approved_path, https_url, loopback_url
from conftest import FakeVault


def wait_task(client, identifier):
    for _ in range(40):
        row = next(t for t in client.get('/tasks').json() if t['id'] == identifier)
        if row['status'] not in {'queued', 'running'}:
            return row
        time.sleep(0.1)
    pytest.fail('Task did not finish')


def test_auth_and_health(client):
    assert client.get('/health', headers={'Authorization': ''}).json()['status'] == 'ok'
    assert client.get('/settings', headers={'Authorization': ''}).status_code == 401
    assert client.get('/settings', headers={'Authorization': 'Bearer wrong'}).status_code == 401
    assert client.get('/settings', headers={'Host': 'attacker.example'}).status_code == 400


def test_default_permissions_are_closed(client):
    settings = client.get('/settings').json()
    assert not any(settings[k] for k in ('microphone', 'screen', 'automation', 'tool_execution', 'cloud_ai_allowed', 'sync_enabled'))
    assert client.post('/tasks', json={'action': 'screen_capture', 'args': {}}).status_code == 400


def test_json_integer_values_are_accepted_for_float_settings(client):
    settings = client.get('/settings').json()
    settings['speech_rate'] = 1
    settings['volume'] = 1
    assert client.patch('/settings', json=settings).status_code == 200
    assert client.patch('/settings', json={'speech_rate': True}).status_code == 400


def test_learning_is_opt_in_and_deletable(client):
    store = client.app.state.store
    store.learn('open_app', {'app': 'notepad'})
    assert client.get('/learning').json() == []
    client.patch('/settings', json={'learning': True})
    for _ in range(3):
        store.learn('open_app', {'app': 'notepad'})
    assert client.get('/learning').json()[0]['count'] == 3
    assert any('notepad' in text for text in client.get('/recommendations').json())
    client.post('/learning/erase', json={'approved': True})
    assert client.get('/learning').json() == []


@pytest.mark.parametrize('values', [{'provider': 'paid'}, {'retention_days': 0}, {'microphone': 'true'}, {'custom_endpoint': 'http://169.254.169.254'}, {'unknown': True}, {'approved_roots': ['/']}])
def test_invalid_settings_rejected(client, values):
    assert client.patch('/settings', json=values).status_code == 400


def test_memory_search_correction_and_deletion(client):
    identifier = client.post('/memories', json={'content': 'Prefer Hindi when discussing calendars'}).json()['id']
    assert client.get('/memories?q=Hindi').json()[0]['id'] == identifier
    changed = client.patch('/memories/' + identifier, json={'content': 'Prefer English'}).json()['id']
    assert not client.get('/memories?q=Hindi').json()
    assert client.get('/memories?q=English').json()[0]['id'] == changed
    client.delete('/memories/' + changed)
    assert client.get('/memories').json() == []


def test_fts_queries_are_safe(client):
    client.post('/memories', json={'content': 'work project'})
    assert client.get('/memories', params={'q': '" OR *; DROP TABLE memories; --'}).status_code == 200
    assert len(client.get('/memories').json()) == 1


def test_snapshot_edit_requires_approval(client, tmp_path):
    project = tmp_path / 'project'
    project.mkdir()
    file = project / 'notes.txt'
    file.write_text('original')
    assert client.patch('/settings', json={'approved_roots': [str(project)]}).status_code == 200
    identifier = client.post('/tasks', json={'action': 'write_file', 'args': {'path': str(file), 'content': 'new'}}).json()['id']
    assert next(t for t in client.get('/tasks').json() if t['id'] == identifier)['status'] == 'awaiting_approval'
    time.sleep(0.6)
    assert file.read_text() == 'original'
    assert client.post(f'/tasks/{identifier}/approve', json={'approved': True}).status_code == 200
    row = wait_task(client, identifier)
    assert row['status'] == 'completed'
    assert file.read_text() == 'new'
    from pathlib import Path
    assert Path(row['result']['snapshot']).read_text() == 'original'
    assert client.post(f'/tasks/{identifier}/approve', json={'approved': True}).status_code == 400


def test_expired_action_is_canceled(client):
    identifier = client.post('/tasks', json={'action': 'gmail_send', 'args': {'to': 'client@example.com', 'subject': 'Update', 'body': 'Reviewed message'}}).json()['id']
    client.app.state.store.execute('UPDATE tasks SET expires=? WHERE id=?', (time.time() - 1, identifier))
    assert client.post(f'/tasks/{identifier}/approve', json={'approved': True}).status_code == 400
    time.sleep(0.7)
    row = next(t for t in client.get('/tasks').json() if t['id'] == identifier)
    assert row['status'] == 'canceled'
    assert 'timed out' in row['error']


def test_action_args_and_unrestricted_commands_rejected(client):
    assert client.post('/tasks', json={'action': 'shell', 'args': {'command': 'rm -rf /'}}).status_code == 400
    assert client.post('/tasks', json={'action': 'reminder', 'args': {'message': 'hello', 'command': 'evil'}}).status_code == 400
    assert client.post('/tasks', json={'action': 'reminder', 'args': {}}).status_code == 400


def test_low_risk_action_really_executes(client):
    identifier = client.post('/tasks', json={'action': 'system_info', 'args': {}}).json()['id']
    row = wait_task(client, identifier)
    assert row['status'] == 'completed'
    assert row['result']['ram_total_gb'] > 0


def test_schedule_executes_and_stop_disables(client):
    client.post('/schedules', json={'action': 'reminder', 'args': {'message': 'Review tests'}, 'interval_seconds': 60, 'next_run': time.time()})
    for _ in range(20):
        if any(e['kind'] == 'reminder' for e in client.get('/events').json()):
            break
        time.sleep(0.1)
    assert any(e['detail'] == 'Review tests' for e in client.get('/events').json() if e['kind'] == 'reminder')
    client.post('/stop')
    assert client.get('/schedules').json()[0]['enabled'] == 0


def test_sensitive_actions_cannot_recur(client):
    assert client.post('/schedules', json={'action': 'gmail_send', 'args': {'to': 'a@example.com', 'subject': 'x', 'body': 'x'}, 'interval_seconds': 60}).status_code == 400


def test_export_and_confirmed_erase(client):
    client.post('/memories', json={'content': 'Private preference'})
    assert len(client.get('/export').json()['memories']) == 1
    assert client.post('/erase', json={'approved': False}).status_code == 400
    assert client.post('/erase', json={'approved': True}).status_code == 200
    assert client.get('/export').json()['memories'] == []


def test_symlink_and_traversal_escape(tmp_path):
    root = tmp_path / 'project'
    root.mkdir()
    outside = tmp_path / 'private'
    outside.mkdir()
    try:
        (root / 'escape').symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip('OS does not permit creating test symlinks')
    for value in (str(root / '..' / 'private' / 'secret'), str(root / 'escape' / 'secret'), str(root / '.git' / 'config')):
        with pytest.raises(ValueError):
            approved_path(value, [str(root)])


@pytest.mark.parametrize('url', ['http://example.com', 'https://user:password@example.com', 'https://127.0.0.1', 'https://169.254.169.254', 'https://localhost', 'https://example.com:8443', 'file:///etc/passwd'])
def test_private_or_insecure_urls_rejected(url):
    with pytest.raises(ValueError):
        https_url(url)


def test_valid_urls():
    assert https_url('https://example.com/path') == 'https://example.com/path'
    assert loopback_url('http://127.0.0.1:11434/') == 'http://127.0.0.1:11434'
    with pytest.raises(ValueError):
        loopback_url('https://example.com')


async def test_ai_failover_without_paid_provider(store, tmp_path, monkeypatch):
    ai = AI(Config(data_dir=tmp_path), store, FakeVault())
    called = []
    store.update_settings({'provider': 'gemini'})
    async def gemini(*args):
        called.append('gemini')
        raise httpx.ConnectError('offline')
    async def ollama(*args):
        called.append('ollama')
        return Reply('local response', 'ollama', 'configured-model', [])
    monkeypatch.setattr(ai, '_gemini', gemini)
    monkeypatch.setattr(ai, '_ollama', ollama)
    reply = await ai.chat([{'role': 'user', 'content': 'hello'}], [])
    assert reply.provider == 'ollama'
    assert called == ['gemini', 'ollama']


async def test_gemini_is_blocked_without_free_confirmation(store, tmp_path):
    vault = FakeVault()
    vault.put('gemini_api_key', 'test-not-a-real-key')
    ai = AI(Config(data_dir=tmp_path), store, vault)
    store.update_settings({'cloud_ai_allowed': True})
    with pytest.raises(ValueError, match='Free tier'):
        await ai.gemini_models()


def test_chat_persists_context_and_tools_stay_disabled(client, monkeypatch):
    seen = []
    async def reply(self, messages, tools, memory=None, image=None):
        seen.append(messages)
        assert tools == []
        return Reply('response', 'ollama', 'test', [])
    monkeypatch.setattr(AI, 'chat', reply)
    first = client.post('/chat', json={'message': 'First request'}).json()
    second = client.post('/chat', json={'message': 'Follow up', 'conversation_id': first['conversation_id']})
    assert second.status_code == 200
    assert len(seen[1]) == 3
    assert len(client.get('/conversations/' + first['conversation_id']).json()) == 4


async def test_restart_does_not_replay_approved_transmission(store, tmp_path):
    from ultron.store import Store
    store.execute("INSERT INTO tasks(id,action,args,status,risk,created) VALUES ('x','gmail_send','{}','running','sensitive',?)", (time.time(),))
    store.execute("INSERT INTO tasks(id,action,args,status,risk,created) VALUES ('y','gmail_send','{}','awaiting_approval','sensitive',?)", (time.time(),))
    store.execute("INSERT INTO tasks(id,action,args,status,risk,created) VALUES ('z','gmail_send','{}','queued','sensitive',?)", (time.time(),))
    restarted = Store(tmp_path / 'ultron.sqlite3')
    assert restarted.rows("SELECT status FROM tasks WHERE id='x'")[0]['status'] == 'interrupted'
    assert restarted.rows("SELECT status FROM tasks WHERE id='y'")[0]['status'] == 'canceled'
    assert restarted.rows("SELECT status FROM tasks WHERE id='z'")[0]['status'] == 'canceled'
    restarted.db.close()


async def test_cancel_active_task(store, tmp_path):
    actions = Actions(store, Google(store, FakeVault()), tmp_path)
    entered = asyncio.Event()
    async def block(name, args):
        entered.set()
        await asyncio.sleep(60)
    actions.execute = block
    engine = TaskEngine(store, actions)
    identifier = engine.submit('system_info', {})
    row = store.rows('SELECT * FROM tasks WHERE id=?', (identifier,))[0]
    task = asyncio.create_task(engine.execute_task(row))
    engine.running[identifier] = task
    await entered.wait()
    engine.cancel(identifier)
    await asyncio.gather(task, return_exceptions=True)
    assert store.rows('SELECT status FROM tasks WHERE id=?', (identifier,))[0]['status'] == 'canceled'


def test_one_time_reminder_and_deleted_memory_tombstone(client):
    identifier = client.post('/tasks', json={'action': 'schedule_reminder', 'args': {'message': 'One time', 'due_at': time.time()+1}}).json()['id']
    assert wait_task(client, identifier)['status'] == 'completed'
    for _ in range(30):
        if any(e['kind']=='reminder' and e['detail']=='One time' for e in client.get('/events').json()):
            break
        time.sleep(0.1)
    assert any(e['kind']=='reminder' and e['detail']=='One time' for e in client.get('/events').json())
    assert client.get('/schedules').json()[0]['enabled'] == 0
    memory = client.post('/memories', json={'content':'Delete me everywhere'}).json()['id']
    client.delete('/memories/'+memory)
    assert client.get('/export').json()['tombstones'][0]['entity_id'] == memory


def test_multistep_tools_run_and_sensitive_steps_pause(client, monkeypatch):
    client.patch('/settings', json={'tool_execution':True})
    calls = []
    async def reply(self, messages, tools, memory=None, image=None):
        calls.append(messages)
        if len(calls)==1:
            return Reply('Checking resources', 'ollama', 'test', [{'action':'system_info','args':{}}])
        assert 'UNTRUSTED TOOL RESULTS' in messages[-1]['content']
        return Reply('Drafting an email for review', 'ollama', 'test', [
            {'action':'gmail_send','args':{'to':'review@example.com','subject':'Resources','body':'Review first'}},
            {'action':'reminder','args':{'message':'Should not run before approval'}}])
    monkeypatch.setattr(AI, 'chat', reply)
    response = client.post('/chat', json={'message':'Check resources and propose an email'})
    assert response.status_code == 200
    tasks = client.get('/tasks').json()
    assert next(t for t in tasks if t['action']=='system_info')['status'] == 'completed'
    assert next(t for t in tasks if t['action']=='gmail_send')['status'] == 'awaiting_approval'
    assert not any(t['action']=='reminder' for t in tasks)


async def test_nonzero_development_check_preserves_failed_outcome(store, tmp_path):
    actions = Actions(store, Google(store, FakeVault()), tmp_path)
    async def fail(name, args):
        return {'exit_code': 1, 'output': 'assertion failed'}
    actions.execute = fail
    engine = TaskEngine(store, actions)
    identifier = engine.submit('system_info', {})
    await engine.execute_task(store.rows('SELECT * FROM tasks WHERE id=?', (identifier,))[0])
    row = store.rows('SELECT * FROM tasks WHERE id=?', (identifier,))[0]
    assert row['status'] == 'failed'
    assert 'assertion failed' in row['result']

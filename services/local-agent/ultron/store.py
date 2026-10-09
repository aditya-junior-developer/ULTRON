import json
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any

DEFAULTS = {
    "provider": "auto", "cloud_ai_allowed": False, "gemini_free_tier_confirmed": False,
    "gemini_model": "", "ollama_model": "qwen3:4b", "approved_roots": [], "microphone": False, "screen": False,
    "camera": False, "automation": False, "tool_execution": False, "learning": False,
    "language": "auto", "voice_enabled": False, "voice_model": "", "whisper_model": "small",
    "wake_model": "", "speech_rate": 1.0, "volume": 0.8,
    "retention_days": 30, "sync_enabled": False, "supabase_url": "",
    "supabase_anon_key": "", "cloud_url": "", "google_client_file": "",
    "google_scopes": ["calendar", "drive", "people"], "custom_endpoint": "",
    "custom_model": "", "custom_free_confirmed": False,
}


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
        PRAGMA journal_mode=WAL;
        PRAGMA foreign_keys=ON;
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS conversations(id TEXT PRIMARY KEY, title TEXT, created REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS messages(id TEXT PRIMARY KEY, conversation_id TEXT REFERENCES conversations(id) ON DELETE CASCADE,
          role TEXT NOT NULL, content TEXT NOT NULL, created REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS memories(id TEXT PRIMARY KEY, content TEXT NOT NULL, created REAL NOT NULL);
        CREATE VIRTUAL TABLE IF NOT EXISTS memory_search USING fts5(id UNINDEXED, content);
        CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY, action TEXT NOT NULL, args TEXT NOT NULL,
          status TEXT NOT NULL, risk TEXT NOT NULL, created REAL NOT NULL, expires REAL,
          result TEXT, error TEXT, schedule_id TEXT);
        CREATE TABLE IF NOT EXISTS schedules(id TEXT PRIMARY KEY, action TEXT NOT NULL, args TEXT NOT NULL,
          interval_seconds INTEGER NOT NULL, next_run REAL NOT NULL, enabled INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY, kind TEXT, detail TEXT, created REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS tombstones(entity_id TEXT NOT NULL, entity_type TEXT NOT NULL, deleted REAL NOT NULL, PRIMARY KEY(entity_id,entity_type));
        CREATE TABLE IF NOT EXISTS patterns(action TEXT NOT NULL, label TEXT NOT NULL, count INTEGER NOT NULL DEFAULT 1, PRIMARY KEY(action,label));
        """)
        if "updated" not in {row[1] for row in self.db.execute("PRAGMA table_info(memories)")}:
            self.db.execute("ALTER TABLE memories ADD COLUMN updated REAL NOT NULL DEFAULT 0")
            self.db.execute("UPDATE memories SET updated=created")
        if "once" not in {row[1] for row in self.db.execute("PRAGMA table_info(schedules)")}:
            self.db.execute("ALTER TABLE schedules ADD COLUMN once INTEGER NOT NULL DEFAULT 0")
        self.db.execute("UPDATE tasks SET status='interrupted', error='Agent restarted during execution' WHERE status='running'")
        self.db.execute("UPDATE tasks SET status='canceled', error='Approval canceled by restart' WHERE status='awaiting_approval'")
        self.db.execute("UPDATE tasks SET status='canceled', error='Approved sensitive action canceled by restart; propose and approve again' WHERE status='queued' AND risk!='low'")
        self.db.commit()

    def execute(self, sql: str, params=()):
        with self.lock:
            cursor = self.db.execute(sql, params)
            self.db.commit()
            return cursor

    def rows(self, sql: str, params=()) -> list[dict]:
        with self.lock:
            return [dict(r) for r in self.db.execute(sql, params).fetchall()]

    def settings(self) -> dict:
        return DEFAULTS | {r["key"]: json.loads(r["value"]) for r in self.rows("SELECT * FROM settings")}

    def update_settings(self, values: dict):
        for key, value in values.items():
            self.execute("INSERT OR REPLACE INTO settings VALUES (?,?)", (key, json.dumps(value)))

    def event(self, kind: str, detail: str):
        self.execute("INSERT INTO events VALUES (?,?,?,?)", (str(uuid.uuid4()), kind, detail[:2000], time.time()))

    def learn(self, action: str, args: dict):
        if not self.settings()["learning"]:
            return
        label = args.get("app") if action == "open_app" else args.get("command") if action == "dev_command" else None
        if label:
            self.execute("INSERT INTO patterns(action,label,count) VALUES (?,?,1) ON CONFLICT(action,label) DO UPDATE SET count=count+1", (action, label))

    def conversation(self, identifier: str | None, title: str) -> str:
        if identifier:
            if not self.rows("SELECT id FROM conversations WHERE id=?", (identifier,)):
                raise ValueError("Conversation not found")
            return identifier
        identifier = str(uuid.uuid4())
        self.execute("INSERT INTO conversations VALUES (?,?,?)", (identifier, title[:80], time.time()))
        return identifier

    def message(self, conversation: str, role: str, content: str):
        self.execute("INSERT INTO messages VALUES (?,?,?,?,?)", (str(uuid.uuid4()), conversation, role, content, time.time()))

    def history(self, conversation: str):
        return self.rows("SELECT role,content FROM (SELECT * FROM messages WHERE conversation_id=? ORDER BY created DESC LIMIT 30) ORDER BY created", (conversation,))

    def remember(self, content: str) -> str:
        identifier = str(uuid.uuid4())
        with self.lock, self.db:
            now = time.time()
            self.db.execute("INSERT INTO memories VALUES (?,?,?,?)", (identifier, content, now, now))
            self.db.execute("INSERT INTO memory_search VALUES (?,?)", (identifier, content))
        return identifier

    def forget(self, identifier: str):
        with self.lock, self.db:
            self.db.execute("DELETE FROM memories WHERE id=?", (identifier,))
            self.db.execute("DELETE FROM memory_search WHERE id=?", (identifier,))
            self.db.execute("INSERT OR REPLACE INTO tombstones VALUES (?,?,?)", (identifier, "memories", time.time()))

    def correct(self, identifier: str, content: str):
        with self.lock, self.db:
            if not self.db.execute("SELECT id FROM memories WHERE id=?", (identifier,)).fetchone():
                raise ValueError("Memory not found")
            self.db.execute("UPDATE memories SET content=?,updated=? WHERE id=?", (content, time.time(), identifier))
            self.db.execute("UPDATE memory_search SET content=? WHERE id=?", (content, identifier))

    def delete_conversation(self, identifier: str):
        with self.lock, self.db:
            self.db.execute("DELETE FROM conversations WHERE id=?", (identifier,))
            self.db.execute("INSERT OR REPLACE INTO tombstones VALUES (?,?,?)", (identifier, "conversations", time.time()))

    def search(self, query: str):
        terms = ' OR '.join('"' + word.replace('"', '""') + '"' for word in query.split()[:12])
        if not terms:
            return self.rows("SELECT * FROM memories ORDER BY created DESC LIMIT 30")
        return self.rows("SELECT m.* FROM memory_search f JOIN memories m ON m.id=f.id WHERE memory_search MATCH ? ORDER BY bm25(memory_search) LIMIT 10", (terms,))

    def purge(self):
        cutoff = time.time() - self.settings()["retention_days"] * 86400
        with self.lock, self.db:
            for row in self.db.execute("SELECT id FROM conversations WHERE created<?", (cutoff,)).fetchall():
                self.db.execute("INSERT OR REPLACE INTO tombstones VALUES (?,?,?)", (row["id"], "conversations", time.time()))
            self.db.execute("DELETE FROM conversations WHERE created<?", (cutoff,))
            self.db.execute("DELETE FROM events WHERE created<?", (cutoff,))
            self.db.execute("DELETE FROM tasks WHERE created<? AND status NOT IN ('running','queued','awaiting_approval')", (cutoff,))

    def export(self) -> dict[str, Any]:
        return {table: self.rows(f"SELECT * FROM {table}") for table in
                ("conversations", "messages", "memories", "tasks", "schedules", "events", "tombstones", "patterns")}

    def erase(self):
        with self.lock, self.db:
            for table in ("conversations", "memories"):
                for row in self.db.execute(f"SELECT id FROM {table}").fetchall():
                    self.db.execute("INSERT OR REPLACE INTO tombstones VALUES (?,?,?)", (row["id"], table, time.time()))
            for table in ("messages", "conversations", "memories", "memory_search", "tasks", "schedules", "events", "patterns"):
                self.db.execute(f"DELETE FROM {table}")

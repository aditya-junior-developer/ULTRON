import time

import httpx

from .config import Vault
from .security import https_url
from .store import Store


class Cloud:
    def __init__(self, store: Store, vault: Vault):
        self.store, self.vault = store, vault

    async def request(self, method, path, body=None):
        s = self.store.settings()
        url = https_url(s["cloud_url"]).rstrip("/")
        token = self.vault.get("cloud_access_token")
        if not token:
            raise ValueError("Sign in to cloud access first")
        async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
            device = self.vault.get("cloud_device_token")
            headers = {"Authorization": "Bearer " + token}
            if device:
                headers["X-ULTRON-Device-Token"] = device
            r = await client.request(method, url + path, headers=headers, json=body)
            if r.status_code == 401:
                refresh = self.vault.get("cloud_refresh_token")
                if not refresh:
                    raise ValueError("Cloud session expired; sign in again")
                auth_url = https_url(s["supabase_url"]).rstrip("/")
                renewed = await client.post(auth_url + "/auth/v1/token?grant_type=refresh_token",
                    headers={"apikey": s["supabase_anon_key"]}, json={"refresh_token": refresh})
                renewed.raise_for_status()
                credentials = renewed.json()
                self.vault.put("cloud_access_token", credentials["access_token"])
                self.vault.put("cloud_refresh_token", credentials["refresh_token"])
                headers["Authorization"] = "Bearer " + credentials["access_token"]
                r = await client.request(method, url + path, headers=headers, json=body)
            r.raise_for_status()
            return r.json()

    async def sync(self):
        if not self.store.settings()["sync_enabled"]:
            raise ValueError("Cloud synchronization is disabled")
        export = self.store.export()
        payload = {key: export[key][-100:] for key in ("conversations", "messages", "memories", "tombstones")}
        parent_ids = {row["id"] for row in payload["conversations"]}
        payload["messages"] = [row for row in payload["messages"] if row["conversation_id"] in parent_ids]
        result = await self.request("POST", "/sync", payload)
        # Merge server records by immutable UUID; no wholesale replacement of local history.
        with self.store.lock, self.store.db:
            for deletion in result.get("tombstones", []):
                table = deletion["entity_type"]
                if table not in {"conversations", "memories"}:
                    continue
                self.store.db.execute(f"DELETE FROM {table} WHERE id=?", (deletion["entity_id"],))
                if table == "memories":
                    self.store.db.execute("DELETE FROM memory_search WHERE id=?", (deletion["entity_id"],))
                self.store.db.execute("INSERT OR REPLACE INTO tombstones VALUES (?,?,?)",
                    (deletion["entity_id"], table, deletion["deleted"]))
            for conversation in result.get("conversations", []):
                self.store.db.execute("INSERT OR IGNORE INTO conversations VALUES (?,?,?)",
                    (conversation["id"], conversation.get("title", ""), conversation["created"]))
            for message in result.get("messages", []):
                if self.store.db.execute("SELECT 1 FROM conversations WHERE id=?", (message["conversation_id"],)).fetchone():
                    self.store.db.execute("INSERT OR IGNORE INTO messages VALUES (?,?,?,?,?)",
                        (message["id"], message["conversation_id"], message["role"], message["content"], message["created"]))
            for memory in result.get("memories", []):
                current = self.store.db.execute("SELECT updated FROM memories WHERE id=?", (memory["id"],)).fetchone()
                if not current:
                    self.store.db.execute("INSERT INTO memories VALUES (?,?,?,?)", (memory["id"], memory["content"], memory["created"], memory["updated"]))
                    self.store.db.execute("INSERT INTO memory_search VALUES (?,?)", (memory["id"], memory["content"]))
                elif memory["updated"] > current["updated"]:
                    self.store.db.execute("UPDATE memories SET content=?,updated=? WHERE id=?", (memory["content"], memory["updated"], memory["id"]))
                    self.store.db.execute("UPDATE memory_search SET content=? WHERE id=?", (memory["content"], memory["id"]))
        self.store.event("cloud_sync", f"Synchronization completed at {int(time.time())}")
        return {"synchronized": True}

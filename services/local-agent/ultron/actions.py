import asyncio
import base64
import json
import os
import platform
import shutil
import subprocess
import threading
import time
import uuid
import webbrowser
from dataclasses import dataclass
from pathlib import Path

import jsonschema
import psutil

from .google import Google
from .security import approved_path, https_url
from .store import Store


@dataclass
class Action:
    name: str
    description: str
    properties: dict
    required: list[str]
    risk: str = "low"
    permission: str | None = None
    scheduled: bool = False

    def schema(self):
        return {"type": "object", "properties": self.properties, "required": self.required, "additionalProperties": False}


def string(description="", maximum=20000):
    return {"type": "string", "description": description, "maxLength": maximum, "minLength": 1}


def action_catalog():
    text, path = string(), string("Absolute path inside a user-approved folder", 4096)
    return [
        Action("system_info", "Read basic system resources", {}, [], scheduled=True),
        Action("reminder", "Record a reminder in the task monitor", {"message": text}, ["message"], scheduled=True),
        Action("schedule_reminder", "Schedule a one-time reminder at a future Unix timestamp, or recur with an explicit interval", {"message": text, "due_at": {"type": "number", "minimum": 0}, "repeat_seconds": {"type": "integer", "minimum": 60, "maximum": 31536000}}, ["message", "due_at"]),
        Action("list_files", "List files in an approved directory", {"path": path}, ["path"], scheduled=True),
        Action("search_files", "Find filenames inside an approved folder; bounded traversal", {"path": path, "query": string(maximum=200)}, ["path", "query"]),
        Action("read_file", "Read a UTF-8 text file in an approved directory", {"path": path}, ["path"], "sensitive"),
        Action("write_file", "Create/edit a text file; preserve an existing file snapshot", {"path": path, "content": {"type": "string", "maxLength": 200000}}, ["path", "content"], "sensitive"),
        Action("delete_file", "Move one approved file into a recovery snapshot; no directory deletion", {"path": path}, ["path"], "sensitive"),
        Action("open_folder", "Open an approved folder", {"path": path}, ["path"], permission="automation"),
        Action("open_app", "Open an allowlisted Windows application", {"app": {"type": "string", "enum": ["notepad", "calculator", "explorer", "chrome"]}}, ["app"], permission="automation"),
        Action("windows", "List visible windows", {}, [], permission="automation"),
        Action("window_control", "Focus, minimize, maximize or close a specific window", {"handle": {"type": "integer", "minimum": 1}, "operation": {"type": "string", "enum": ["focus", "minimize", "maximize", "close"]}}, ["handle", "operation"], "sensitive", "automation"),
        Action("set_volume", "Set speaker volume from 0 to 100", {"value": {"type": "integer", "minimum": 0, "maximum": 100}}, ["value"], permission="automation"),
        Action("set_brightness", "Set supported monitor brightness from 0 to 100", {"value": {"type": "integer", "minimum": 0, "maximum": 100}}, ["value"], "sensitive", "automation"),
        Action("screen_capture", "Capture the screen once, in memory only", {}, [], "sensitive", "screen"),
        Action("screen_click", "Click a specified screen location", {"x": {"type": "integer", "minimum": 0}, "y": {"type": "integer", "minimum": 0}}, ["x", "y"], "sensitive", "automation"),
        Action("screen_type", "Type approved text in the active application", {"text": string(maximum=5000)}, ["text"], "sensitive", "automation"),
        Action("dev_command", "Run a fixed development check without a shell", {"path": path, "command": {"type": "string", "enum": ["pytest", "npm_test", "npm_build", "git_status", "git_diff"]}}, ["path", "command"], "sensitive"),
        Action("browser_navigate", "Navigate the isolated browser to a public HTTPS page", {"url": string(maximum=4096)}, ["url"], permission="automation"),
        Action("browser_new_tab", "Open a new isolated browser tab", {"url": string(maximum=4096)}, ["url"], permission="automation"),
        Action("browser_download", "Download to a new file inside an approved folder", {"selector": string(maximum=500), "path": path}, ["selector", "path"], "sensitive", "automation"),
        Action("browser_read", "Read isolated browser page text as untrusted data", {}, [], "sensitive", "automation"),
        Action("browser_tabs", "List isolated browser tabs", {}, [], permission="automation"),
        Action("browser_switch", "Switch to an isolated browser tab", {"index": {"type": "integer", "minimum": 0}}, ["index"], permission="automation"),
        Action("browser_fill", "Fill one field without submitting", {"selector": string(maximum=500), "value": text}, ["selector", "value"], "sensitive", "automation"),
        Action("browser_click", "Click a page control; may submit or transmit information", {"selector": string(maximum=500)}, ["selector"], "sensitive", "automation"),
        Action("gmail_list", "List Gmail message IDs", {"query": text}, [], "sensitive"),
        Action("gmail_read", "Read a selected Gmail message", {"id": string(maximum=200)}, ["id"], "sensitive"),
        Action("gmail_draft", "Save an email draft without sending", {"to": string(maximum=500), "subject": string(maximum=500), "body": text}, ["to", "subject", "body"], "sensitive"),
        Action("gmail_send", "SEND an email to the displayed recipient after explicit approval", {"to": string(maximum=500), "subject": string(maximum=500), "body": text}, ["to", "subject", "body"], "sensitive"),
        Action("calendar_list", "Read upcoming calendar events", {"from_time": string(maximum=100)}, ["from_time"], "sensitive"),
        Action("calendar_create", "Create a calendar event", {"title": string(maximum=500), "start": string(maximum=100), "end": string(maximum=100), "timezone": string(maximum=100), "description": text}, ["title", "start", "end"], "sensitive"),
        Action("drive_list", "List files authorized for this app through Drive file scope", {}, [], "sensitive"),
        Action("drive_backup", "Upload an export containing private ULTRON data to Google Drive", {}, [], "sensitive"),
        Action("contacts_list", "Read authorized Google contacts", {}, [], "sensitive"),
        Action("meet_recordings", "List accessible meeting recordings; does not record a meeting", {"conference": string(maximum=500)}, ["conference"], "sensitive"),
        Action("meet_transcripts", "List accessible meeting transcripts; does not join a meeting", {"conference": string(maximum=500)}, ["conference"], "sensitive"),
    ]


class Actions:
    def __init__(self, store: Store, google: Google, data_dir: Path):
        self.store, self.google, self.data_dir = store, google, data_dir
        self.catalog = {a.name: a for a in action_catalog()}
        self.context = None
        self.page = None
        self.playwright = None
        self.download_allowed = False
        self.cancel_flag = threading.Event()
        self.desktop_lock = asyncio.Lock()

    def validate(self, name: str, args: dict) -> Action:
        action = self.catalog.get(name)
        if not action:
            raise ValueError("Unknown action")
        try:
            jsonschema.validate(args, action.schema())
        except jsonschema.ValidationError as exc:
            raise ValueError("Invalid action arguments: " + exc.message) from exc
        if action.permission and not self.store.settings()[action.permission]:
            raise ValueError(f"Enable {action.permission} permission in Settings first")
        if "path" in args:
            approved_path(args["path"], self.store.settings()["approved_roots"])
        if "url" in args:
            https_url(args["url"])
        return action

    def tools(self):
        return [{"name": a.name, "description": a.description, "parameters": a.schema()} for a in self.catalog.values()
                if not a.permission or self.store.settings()[a.permission]]

    async def close(self):
        if self.context:
            await self.context.close()
        if self.playwright:
            await self.playwright.stop()
        self.context = self.page = self.playwright = None

    async def browser(self):
        if self.context is None:
            from playwright.async_api import async_playwright
            self.playwright = await async_playwright().start()
            self.context = await self.playwright.chromium.launch_persistent_context(
                str(self.data_dir / "browser"), headless=False, accept_downloads=True,
                channel="chrome" if os.name == "nt" else None)
            self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()
            def download_guard(download):
                if not self.download_allowed:
                    asyncio.create_task(download.cancel())
            self.page.on("download", download_guard)
            async def guard(route):
                try:
                    https_url(route.request.url)
                    await route.continue_()
                except ValueError:
                    await route.abort()
            await self.context.route("**/*", guard)
        return self.page

    async def execute(self, name: str, args: dict):
        self.validate(name, args)
        if name.startswith("browser_"):
            async with self.desktop_lock:
                page = await self.browser()
                if name == "browser_navigate":
                    await page.goto(https_url(args["url"]), wait_until="domcontentloaded", timeout=30000)
                    return {"url": page.url, "title": await page.title()}
                if name == "browser_new_tab":
                    self.page = await self.context.new_page()
                    await self.page.goto(https_url(args["url"]), wait_until="domcontentloaded", timeout=30000)
                    return {"url": self.page.url}
                if name == "browser_read":
                    return {"untrusted_page_text": (await page.locator("body").inner_text())[:24000]}
                if name == "browser_tabs":
                    return [{"index": i, "url": p.url} for i, p in enumerate(self.context.pages)]
                if name == "browser_switch":
                    self.page = self.context.pages[args["index"]]
                    await self.page.bring_to_front()
                    return {"url": self.page.url}
                if name == "browser_fill":
                    await page.locator(args["selector"]).fill(args["value"], timeout=10000)
                    return {"filled": True}
                if name == "browser_click":
                    await page.locator(args["selector"]).click(timeout=10000)
                    return {"clicked": True, "url": page.url}
                if name == "browser_download":
                    target = approved_path(args["path"], self.store.settings()["approved_roots"])
                    if target.exists() or not target.parent.is_dir():
                        raise ValueError("Choose a new file inside an existing approved folder")
                    self.download_allowed = True
                    try:
                        async with page.expect_download(timeout=30000) as download_info:
                            await page.locator(args["selector"]).click(timeout=10000)
                        download = await download_info.value
                        https_url(download.url)
                        await download.save_as(str(target))
                        return {"downloaded": str(target)}
                    finally:
                        self.download_allowed = False
        if name == "dev_command":
            directory = approved_path(args["path"], self.store.settings()["approved_roots"], True)
            import sys
            commands = {"pytest": [sys.executable, "-m", "pytest"], "npm_test": ["npm", "test"],
                        "npm_build": ["npm", "run", "build"], "git_status": ["git", "status", "--short"], "git_diff": ["git", "diff", "--stat"]}
            cmd = commands[args["command"]]
            if os.name == "nt" and cmd[0] == "npm":
                cmd[0] = "npm.cmd"
            # Fixed arguments, no model-controlled command strings or shell.
            process = await asyncio.create_subprocess_exec(*cmd, cwd=directory, stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT, start_new_session=os.name != "nt")
            try:
                output, _ = await asyncio.wait_for(process.communicate(), 120)
            except BaseException:
                if process.returncode is None:
                    if os.name == "nt":
                        await asyncio.create_subprocess_exec("taskkill", "/PID", str(process.pid), "/T", "/F")
                    else:
                        import signal
                        os.killpg(process.pid, signal.SIGKILL)
                    await process.wait()
                raise
            return {"exit_code": process.returncode, "output": output.decode(errors="replace")[-24000:]}
        if name.startswith(("gmail_", "calendar_", "drive_", "contacts_", "meet_")):
            return await asyncio.to_thread(self.google.execute, name, args)
        async with self.desktop_lock:
            self.cancel_flag.clear()
            work = asyncio.create_task(asyncio.to_thread(self._local, name, args))
            try:
                return await asyncio.shield(work)
            except asyncio.CancelledError:
                self.cancel_flag.set()
                # Keep the desktop lock until the underlying thread actually stops.
                await asyncio.shield(work)
                raise

    def _local(self, name, args):
        settings = self.store.settings()
        if name == "system_info":
            memory = psutil.virtual_memory()
            return {"os": platform.system(), "cpu_percent": psutil.cpu_percent(), "ram_total_gb": round(memory.total / 2**30, 1), "ram_available_gb": round(memory.available / 2**30, 1)}
        if name == "reminder":
            self.store.event("reminder", args["message"])
            return {"message": args["message"]}
        if name == "schedule_reminder":
            if args["due_at"] <= time.time():
                raise ValueError("Reminder timestamp must be in the future")
            identifier = str(uuid.uuid4())
            self.store.execute("INSERT INTO schedules(id,action,args,interval_seconds,next_run,enabled,once) VALUES (?,?,?,?,?,1,?)",
                (identifier, "reminder", json.dumps({"message": args["message"]}), args.get("repeat_seconds", 60), args["due_at"], 0 if args.get("repeat_seconds") else 1))
            return {"schedule_id": identifier, "due_at": args["due_at"], "recurring": bool(args.get("repeat_seconds"))}
        if name in {"list_files", "read_file", "write_file", "delete_file", "open_folder"}:
            path = approved_path(args["path"], settings["approved_roots"])
            if name == "list_files":
                return [{"name": p.name, "directory": p.is_dir()} for p in list(path.iterdir())[:200]]
            if name == "read_file":
                if path.stat().st_size > 200000:
                    raise ValueError("Text files must be below 200 KB")
                return {"path": str(path), "content": path.read_text(encoding="utf-8")}
            if name in {"write_file", "delete_file"}:
                if path.exists():
                    if not path.is_file() or path.stat().st_size > 10_000_000:
                        raise ValueError("Only individual files under 10 MB may be modified")
                    backup = self.data_dir / "snapshots" / (str(uuid.uuid4()) + "-" + path.name)
                    backup.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(path, backup)
                    backup.with_suffix(backup.suffix + ".metadata.json").write_text(json.dumps({"original": str(path), "created": time.time()}))
                elif name == "delete_file":
                    raise ValueError("File does not exist")
                if name == "delete_file":
                    path.unlink()
                else:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(args["content"], encoding="utf-8")
                return {"path": str(path), "operation": name, "snapshot": str(backup) if 'backup' in locals() else None}
            if not path.is_dir():
                raise ValueError("Select a directory")
            if os.name != "nt":
                raise ValueError("Folder opening requires the Windows desktop agent")
            os.startfile(path)
            return {"opened": str(path)}
        if name == "search_files":
            root = approved_path(args["path"], settings["approved_roots"], True)
            found, scanned = [], 0
            for directory, directories, files in os.walk(root, followlinks=False):
                directories[:] = [d for d in directories if d not in {".git", "node_modules", ".venv", ".ssh", ".aws"}]
                scanned += 1
                for filename in files:
                    if args["query"].casefold() in filename.casefold():
                        candidate = Path(directory) / filename
                        try:
                            found.append(str(approved_path(str(candidate), settings["approved_roots"])))
                        except ValueError:
                            pass
                    if len(found) >= 200:
                        return {"files": found, "truncated": True}
                if scanned >= 500:
                    return {"files": found, "truncated": True}
            return {"files": found, "truncated": False}
        if name == "screen_capture":
            import mss
            import mss.tools
            with mss.mss() as capture:
                shot = capture.grab(capture.monitors[1])
                png = mss.tools.to_png(shot.rgb, shot.size)
            return {"image": base64.b64encode(png).decode(), "mime": "image/png", "stored": False}
        if name in {"screen_click", "screen_type"}:
            import pyautogui
            pyautogui.FAILSAFE = True
            if name == "screen_click":
                width, height = pyautogui.size()
                if args["x"] >= width or args["y"] >= height:
                    raise ValueError("Click is outside the screen")
                pyautogui.click(args["x"], args["y"])
            else:
                if not args["text"].isascii():
                    raise ValueError("Visual typing supports ASCII; use native file or browser tools for Unicode")
                for character in args["text"]:
                    if self.cancel_flag.is_set():
                        raise ValueError("Typing canceled")
                    pyautogui.write(character)
                    time.sleep(0.02)
            return {"completed": True}
        if name == "set_brightness":
            import screen_brightness_control as brightness
            brightness.set_brightness(args["value"])
            return {"brightness": args["value"]}
        if os.name != "nt":
            raise ValueError("This action requires the Windows desktop agent")
        if name == "open_app":
            applications = {"notepad": "notepad.exe", "calculator": "calc.exe", "explorer": "explorer.exe"}
            if args["app"] == "chrome":
                webbrowser.open("https://www.google.com")
            else:
                subprocess.Popen([applications[args["app"]]], shell=False)
            return {"opened": args["app"]}
        if name in {"windows", "window_control"}:
            import win32gui
            import win32con
            if name == "windows":
                windows = []
                win32gui.EnumWindows(lambda handle, _: windows.append({"handle": handle, "title": win32gui.GetWindowText(handle)})
                    if win32gui.IsWindowVisible(handle) and win32gui.GetWindowText(handle) else None, None)
                return windows
            handle = args["handle"]
            if not win32gui.IsWindow(handle):
                raise ValueError("Window no longer exists")
            operation = args["operation"]
            if operation == "focus":
                win32gui.ShowWindow(handle, win32con.SW_RESTORE)
                win32gui.SetForegroundWindow(handle)
            elif operation == "close":
                win32gui.PostMessage(handle, win32con.WM_CLOSE, 0, 0)
            else:
                win32gui.ShowWindow(handle, win32con.SW_MINIMIZE if operation == "minimize" else win32con.SW_MAXIMIZE)
            return {"operation": operation}
        if name == "set_volume":
            import comtypes
            from pycaw.pycaw import AudioUtilities
            comtypes.CoInitialize()
            try:
                AudioUtilities.GetSpeakers().EndpointVolume.SetMasterVolumeLevelScalar(args["value"] / 100, None)
            finally:
                comtypes.CoUninitialize()
            return {"volume": args["value"]}
        raise ValueError("Unsupported local action")


class TaskEngine:
    def __init__(self, store: Store, actions: Actions):
        self.store, self.actions = store, actions
        self.running: dict[str, asyncio.Task] = {}
        self.stop_event = asyncio.Event()
        self.semaphore = asyncio.Semaphore(2)

    def submit(self, name: str, args: dict, schedule_id=None):
        action = self.actions.validate(name, args)
        identifier = str(uuid.uuid4())
        status = "awaiting_approval" if action.risk != "low" else "queued"
        self.store.execute("INSERT INTO tasks (id,action,args,status,risk,created,expires,schedule_id) VALUES (?,?,?,?,?,?,?,?)",
            (identifier, name, json.dumps(args), status, action.risk, time.time(), time.time() + 300 if status == "awaiting_approval" else None, schedule_id))
        self.store.event("task_proposed", f"{identifier}: {name} ({status})")
        return identifier

    def approve(self, identifier: str, approve: bool):
        now = time.time()
        changed = self.store.execute("UPDATE tasks SET status=? WHERE id=? AND status='awaiting_approval' AND expires>?",
            ("queued" if approve else "canceled", identifier, now)).rowcount
        if not changed:
            raise ValueError("Approval expired or task is no longer awaiting approval")
        self.store.event("task_approved" if approve else "task_rejected", identifier)

    def cancel(self, identifier: str):
        if identifier in self.running:
            self.running[identifier].cancel()
        self.store.execute("UPDATE tasks SET status='canceled',error='Canceled by user' WHERE id=? AND status IN ('queued','running','awaiting_approval')", (identifier,))
        self.store.event("task_canceled", identifier)

    def emergency_stop(self):
        for task in self.running.values():
            task.cancel()
        self.store.execute("UPDATE tasks SET status='canceled',error='Emergency stop requested' WHERE status IN ('queued','running','awaiting_approval')")
        self.store.execute("UPDATE schedules SET enabled=0")
        self.store.update_settings({"tool_execution": False, "microphone": False})
        self.store.event("emergency_stop", "Task cancellation requested; schedules disabled. Already transmitted external actions cannot be undone.")

    async def execute_task(self, row):
        identifier = row["id"]
        try:
            async with self.semaphore:
                if not self.store.execute("UPDATE tasks SET status='running' WHERE id=? AND status='queued'", (identifier,)).rowcount:
                    return
                result = await asyncio.wait_for(self.actions.execute(row["action"], json.loads(row["args"])), timeout=180)
                if isinstance(result, dict) and result.get("exit_code", 0) != 0:
                    error = f"Development check exited with status {result['exit_code']}"
                    self.store.execute("UPDATE tasks SET status='failed',result=?,error=? WHERE id=? AND status='running'", (json.dumps(result), error, identifier))
                    self.store.event("task_failed", f"{identifier}: {error}")
                    return
                # Captures are returned temporarily through the task endpoint, not stored in SQLite.
                if isinstance(result, dict) and "image" in result:
                    result = {"captured": True, "stored": False, "message": "Use Screen analysis for transient capture and analysis"}
                self.store.execute("UPDATE tasks SET status='completed',result=? WHERE id=? AND status='running'", (json.dumps(result), identifier))
                self.store.event("task_completed", f"{identifier}: {row['action']}")
                self.store.learn(row["action"], json.loads(row["args"]))
        except asyncio.CancelledError:
            self.store.execute("UPDATE tasks SET status='canceled',error='Cancellation requested; in-flight external operations may have completed' WHERE id=?", (identifier,))
            raise
        except Exception as exc:
            # Actionable error, without credentials or external request bodies.
            error = str(exc)[:1000] if isinstance(exc, (ValueError, FileNotFoundError, ImportError)) else f"{type(exc).__name__}: operation failed; check configuration and authorization"
            self.store.execute("UPDATE tasks SET status='failed',error=? WHERE id=? AND status='running'", (error, identifier))
            self.store.event("task_failed", f"{identifier}: {error}")
        finally:
            self.running.pop(identifier, None)

    async def run(self):
        while not self.stop_event.is_set():
            now = time.time()
            expired = self.store.execute("UPDATE tasks SET status='canceled',error='Approval timed out after five minutes' WHERE status='awaiting_approval' AND expires<=?", (now,)).rowcount
            if expired:
                self.store.event("approval_expired", f"Canceled {expired} unconfirmed action(s)")
            for schedule in self.store.rows("SELECT * FROM schedules WHERE enabled=1 AND next_run<=?", (now,)):
                self.store.execute("UPDATE schedules SET next_run=?,enabled=? WHERE id=?", (now + schedule["interval_seconds"], 0 if schedule["once"] else 1, schedule["id"]))
                try:
                    self.submit(schedule["action"], json.loads(schedule["args"]), schedule["id"])
                except ValueError as exc:
                    self.store.event("schedule_failed", str(exc))
            for row in self.store.rows("SELECT * FROM tasks WHERE status='queued' ORDER BY created LIMIT 2"):
                if row["id"] not in self.running:
                    self.running[row["id"]] = asyncio.create_task(self.execute_task(row))
            try:
                await asyncio.wait_for(self.stop_event.wait(), timeout=0.5)
            except TimeoutError:
                pass

    async def close(self):
        self.stop_event.set()
        for task in list(self.running.values()):
            task.cancel()
        await asyncio.gather(*list(self.running.values()), return_exceptions=True)
        await self.actions.close()

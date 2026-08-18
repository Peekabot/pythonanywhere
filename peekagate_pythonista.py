#!/usr/bin/env python3
"""Peekagate Pythonista worker — thin poll loop + action dispatch."""
import requests
import time
import platform
from datetime import datetime
from pathlib import Path

BASE = "https://peekabot.pythonanywhere.com"
INTERVAL = 15
LAST = {}
NODE = "pythonista"

def hardware():
    info = {
        "platform": platform.platform()[:80],
        "machine": platform.machine(),
        "python": platform.python_version(),
        "cwd": str(Path.cwd()),
        "home": str(Path.home()),
    }
    try:
        import objc_util
        d = objc_util.ObjCClass("UIDevice").currentDevice()
        d.setBatteryMonitoringEnabled_(True)
        info["battery"] = round(float(d.batteryLevel()) * 100, 1)
    except Exception:
        pass
    try:
        import shutil
        disk = shutil.disk_usage(str(Path.home()))
        info["disk_free_mb"] = disk.free // (1024 * 1024)
    except Exception:
        pass
    return info

def list_paths(path=".", limit=40):
    p = Path(path).expanduser()
    if not p.exists():
        return {"error": f"missing {p}"}
    if p.is_file():
        return {"file": str(p), "size": p.stat().st_size}
    items = []
    try:
        for c in sorted(p.iterdir())[:limit]:
            items.append(("d " if c.is_dir() else "f ") + c.name)
    except Exception:
        return {"error": f"cannot read {p}"}
    return {"path": str(p.resolve()), "entries": items}

def read_file(path, max_chars=8000):
    p = Path(path).expanduser()
    if not p.is_file():
        return {"read_error": str(p)}
    try:
        text = p.read_text(errors="replace")[:max_chars]
        return {"read": {"path": str(p), "text": text}}
    except Exception as e:
        return {"read_error": str(e)}

def list_scripts():
    root = Path(".").resolve()
    names = sorted(p.name for p in root.glob("*.py"))
    return {"scripts": names}

def search_files(q, max_hits=20):
    q = (q or "").lower()
    hits = []
    root = Path(".").resolve()
    for p in root.glob("*.py"):
        try:
            for i, line in enumerate(p.read_text(errors="replace").splitlines(), 1):
                if q and q in line.lower():
                    hits.append({"file": p.name, "line": i, "text": line.strip()[:120]})
                    if len(hits) >= max_hits:
                        break
        except Exception:
            pass
        if len(hits) >= max_hits:
            break
    return {"search": {"q": q, "hits": hits}}

def push_state(extra=None):
    global LAST
    if extra:
        LAST.update(extra)
    payload = {
        "source": NODE,
        "status": "online",
        "time": datetime.utcnow().isoformat() + "Z",
        "hw": hardware(),
        "note": "alive",
    }
    payload.update(LAST)
    try:
        r = requests.post(f"{BASE}/api/state", json=payload, timeout=12)
        print(f"\u2191 {r.status_code}")
        return r.json() if r.ok else None
    except Exception as e:
        print(f"\u2191 fail {e}")
        return None

def pull_commands():
    try:
        r = requests.get(f"{BASE}/api/commands", timeout=12)
        return r.json() if r.status_code == 200 else []
    except Exception as e:
        print(f"\u2193 fail {e}")
        return []

def for_me(cmd):
    t = cmd.get("target")
    if not t or t in ("all", NODE, "pythonista"):
        return True
    return False

def notify(msg):
    try:
        import notification
        notification.schedule("Peekagate", str(msg), 0)
        print(f"notify: {msg}")
    except Exception:
        print(f"notify: {msg}")

def upload_file(path, tag="general"):
    p = Path(path).expanduser()
    if not p.is_file():
        return {"upload_error": f"missing {p}"}
    try:
        with open(p, "rb") as f:
            r = requests.post(
                f"{BASE}/upload",
                files={"file": (p.name, f)},
                data={"tag": tag},
                timeout=60,
            )
        print(f"upload {r.status_code}")
        return r.json() if r.ok else {"upload_error": str(r.status_code)}
    except Exception as e:
        return {"upload_error": str(e)}

def run_cmd(cmd):
    if not isinstance(cmd, dict):
        return
    if not for_me(cmd):
        print("skip target", cmd.get("target"))
        return
    action = cmd.get("action")
    print("cmd:", action)

    if action == "ping":
        push_state({"pong": datetime.utcnow().isoformat() + "Z"})
    elif action in ("hw", "hardware"):
        push_state({"hw_report": hardware()})
    elif action in ("ls", "list"):
        push_state({"ls": list_paths(cmd.get("path", "."))})
    elif action == "read":
        push_state(read_file(cmd.get("path", "")))
    elif action == "echo":
        push_state({"last_echo": cmd.get("message")})
    elif action == "notify":
        notify(cmd.get("message", "Peekagate alert"))
    elif action == "upload":
        push_state(upload_file(cmd.get("path", ""), cmd.get("tag", "general")))
    elif action == "open_url":
        import webbrowser
        url = cmd.get("url", BASE + "/")
        webbrowser.open(url)
        push_state({"opened": url})
    elif action == "scripts":
        push_state(list_scripts())
    elif action == "search":
        push_state(search_files(cmd.get("q", "")))
    else:
        print("unknown:", action)

def main():
    print("Peekagate Pythonista ->", BASE)
    print(platform.platform())
    push_state({"startup": datetime.utcnow().isoformat() + "Z"})
    n = 0
    while True:
        try:
            for c in pull_commands():
                run_cmd(c)
            n += 1
            if n % 3 == 0:
                push_state()
        except KeyboardInterrupt:
            push_state({"status": "offline"})
            print("offline")
            break
        except Exception as e:
            print("loop", e)
        time.sleep(INTERVAL)

if __name__ == "__main__":
    main()

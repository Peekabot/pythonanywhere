#!/usr/bin/env python3
"""Peekagate iSH node — paths, tools, light hardware. Keep server unchanged."""
import json, os, platform, shutil, subprocess, time
from datetime import datetime
from pathlib import Path

try:
    import requests
except ImportError:
    os.system("apk add py3-requests 2>/dev/null")
    import requests

BASE = "https://peekabot.pythonanywhere.com"
INTERVAL = 20
ROOT = Path.home()

def sh(cmd, timeout=15):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return (r.stdout or "") + (r.stderr or ""), r.returncode
    except Exception as e:
        return str(e), 1

def hardware():
    mem = ""
    out, _ = sh("free -m 2>/dev/null | awk '/Mem:/{print $2,$3}'")
    if out.strip():
        parts = out.split()
        if len(parts) >= 2:
            mem = f"{parts[1]}/{parts[0]}MB"
    disk = shutil.disk_usage(str(ROOT))
    return {
        "platform": platform.platform()[:80],
        "machine": platform.machine(),
        "mem": mem or None,
        "disk_free_mb": disk.free // (1024 * 1024),
        "cwd": str(Path.cwd()),
        "home": str(ROOT),
    }

def list_paths(path=".", limit=40):
    p = Path(path).expanduser()
    if not p.exists():
        return {"error": f"missing {p}"}
    if p.is_file():
        return {"file": str(p), "size": p.stat().st_size}
    items = []
    for c in sorted(p.iterdir())[:limit]:
        items.append(("d " if c.is_dir() else "f ") + c.name)
    return {"path": str(p.resolve()), "entries": items}

def push_state(extra=None):
    payload = {
        "source": "ish",
        "status": "online",
        "time": datetime.utcnow().isoformat() + "Z",
        "hw": hardware(),
        "note": "ish-node",
    }
    if extra:
        payload.update(extra)
    try:
        r = requests.post(f"{BASE}/api/state", json=payload, timeout=12)
        print("\u2191", r.status_code)
        return r.json() if r.ok else None
    except Exception as e:
        print("\u2191 fail", e)
        return None

def pull_commands():
    try:
        r = requests.get(f"{BASE}/api/commands", timeout=12)
        return r.json() if r.status_code == 200 else []
    except Exception as e:
        print("\u2193 fail", e)
        return []

def run_cmd(cmd):
    if not isinstance(cmd, dict):
        return
    a = cmd.get("action")
    print("cmd:", a, cmd)

    if a == "ping":
        push_state({"pong": datetime.utcnow().isoformat() + "Z"})
    elif a in ("hw", "hardware"):
        push_state({"hw_report": hardware()})
    elif a in ("ls", "list"):
        push_state({"ls": list_paths(cmd.get("path", str(ROOT)))})
    elif a == "read":
        path = Path(cmd.get("path", "")).expanduser()
        if not path.is_file():
            push_state({"read_error": str(path)})
            return
        text = path.read_text(errors="replace")[:8000]
        push_state({"read": {"path": str(path), "text": text}})
    elif a == "run":
        c = cmd.get("cmd", "")
        if not c:
            return
        out, code = sh(c)
        push_state({"run": {"cmd": c, "code": code, "out": out[:6000]}})
    elif a == "echo":
        push_state({"last_echo": cmd.get("message")})
    else:
        print("unknown", a)

def main():
    print("Peekagate iSH \u2192", BASE)
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
            break
        except Exception as e:
            print("loop", e)
        time.sleep(INTERVAL)

if __name__ == "__main__":
    main()

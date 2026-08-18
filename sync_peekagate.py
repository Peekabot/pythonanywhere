# sync_peekagate.py — pull tracked files from GitHub into this folder
import os
import requests

REPO = "Peekabot/pythonanywhere"
BRANCH = "main"
BASE = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}"
FILES = [
    "bagster.md",
    "peekagate_ish.py",
    "peekagate_pythonista.py",
    "sync_peekagate.py",
]

def sync():
    here = os.path.dirname(os.path.abspath(__file__)) or "."
    for name in FILES:
        url = f"{BASE}/{name}"
        try:
            r = requests.get(url, timeout=30)
            r.raise_for_status()
            path = os.path.join(here, name)
            with open(path, "w", encoding="utf-8") as f:
                f.write(r.text)
            print("OK", name, len(r.text), "bytes")
        except Exception as e:
            print("FAIL", name, e)

if __name__ == "__main__":
    sync()

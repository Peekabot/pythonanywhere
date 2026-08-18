from flask import Flask, jsonify, request, render_template_string, send_file
from datetime import datetime
import json, os, uuid
from werkzeug.utils import secure_filename

app = Flask(__name__)

# ===== CONFIG =====
BASE_DIR = "/home/peekabot/mysite"
STATE_FILE = f"{BASE_DIR}/state.json"
CMD_FILE = f"{BASE_DIR}/commands.json"
FILES_DIR = f"{BASE_DIR}/files"
os.makedirs(FILES_DIR, exist_ok=True)

# ===== HELPERS =====
def load(path, default):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return default

def save(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

def get_file_metadata(file_id):
    meta_file = f"{FILES_DIR}/{file_id}.meta.json"
    if os.path.exists(meta_file):
        with open(meta_file) as f:
            return json.load(f)
    return None

def list_files(tag=None, limit=50):
    files = []
    if not os.path.isdir(FILES_DIR):
        return []
    for fname in os.listdir(FILES_DIR):
        if fname.endswith(".meta.json"):
            with open(f"{FILES_DIR}/{fname}") as f:
                meta = json.load(f)
                if not tag or meta.get("tag") == tag:
                    files.append(meta)
    files.sort(key=lambda x: x.get("uploaded", ""), reverse=True)
    return files[:limit]

# ===== DASHBOARD =====
@app.route("/")
def dash():
    state = load(STATE_FILE, {"status": "unknown", "updated": None})
    recent_files = list_files(limit=10)
    cmds = load(CMD_FILE, [])
    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Peekagate</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body { font-family: -apple-system, monospace; padding: 20px; background: #f5f5f5; max-width: 1100px; margin: 0 auto; }
            .card { background: white; padding: 20px; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); margin-bottom: 16px; }
            .status { display: inline-block; padding: 4px 12px; border-radius: 12px; font-weight: bold; }
            .online { background: #4CAF50; color: white; }
            .offline { background: #f44336; color: white; }
            .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 12px; }
            .file-item { background: #f8f9fa; padding: 12px; border-radius: 8px; border-left: 3px solid #4CAF50; }
            .file-tag { background: #e9ecef; padding: 2px 8px; border-radius: 4px; font-size: 0.8em; }
            .meta { color: #666; font-size: 0.85em; }
            pre { margin: 0; white-space: pre-wrap; font-size: 0.85em; }
        </style>
    </head>
    <body>
        <h1>Peekagate</h1>

        <div class="card">
            <h2>Device State</h2>
            <div>
                Status:
                <span class="status {{ 'online' if state.get('status') == 'online' else 'offline' }}">
                    {{ state.get('status', 'unknown') }}
                </span>
                {% if state.get('battery') is not none %}
                    | Battery {{ state.battery }}%
                {% endif %}
            </div>
            <div class="meta">Updated: {{ state.get('updated', 'never') }}</div>
            <details><summary>Full state</summary><pre>{{ state|tojson(indent=2) }}</pre></details>
        </div>

        <div class="card">
            <h2>Recent Files</h2>
            <div class="grid">
                {% for file in recent_files %}
                <div class="file-item">
                    <div><strong>{{ file.filename }}</strong></div>
                    <div><span class="file-tag">{{ file.tag or 'untagged' }}</span></div>
                    <div class="meta">{{ (file.size / 1024)|round(1) }} KB · {{ file.uploaded[:19] }}</div>
                    <a href="/file/{{ file.id }}">Download</a>
                </div>
                {% else %}
                <div class="meta">No files yet</div>
                {% endfor %}
            </div>
        </div>

        <div class="card">
            <h2>Pending Commands</h2>
            {% if cmds %}
                {% for cmd in cmds %}
                    <div>{{ loop.index }}. {{ cmd.action }} {{ cmd.get('message', '') }}</div>
                {% endfor %}
            {% else %}
                <div class="meta">No commands queued</div>
            {% endif %}
        </div>
    </body>
    </html>
    """, state=state, recent_files=recent_files, cmds=cmds)

# ===== FILE MANAGER =====
@app.route("/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    file = request.files["file"]
    tag = request.form.get("tag", "general")
    if not file.filename:
        return jsonify({"error": "Empty filename"}), 400

    file_id = str(uuid.uuid4())[:8]
    filename = secure_filename(file.filename)
    file_path = f"{FILES_DIR}/{file_id}.data"
    file.save(file_path)

    meta = {
        "id": file_id,
        "filename": filename,
        "tag": tag,
        "size": os.path.getsize(file_path),
        "uploaded": datetime.utcnow().isoformat() + "Z",
    }
    with open(f"{FILES_DIR}/{file_id}.meta.json", "w") as f:
        json.dump(meta, f, indent=2)
    return jsonify({"ok": True, "file": meta})

@app.route("/list", methods=["GET"])
def list_files_route():
    tag = request.args.get("tag")
    limit = int(request.args.get("limit", 50))
    files = list_files(tag, limit)
    return jsonify({"files": files, "count": len(files)})

@app.route("/file/<file_id>", methods=["GET"])
def get_file(file_id):
    meta = get_file_metadata(file_id)
    if not meta:
        return jsonify({"error": "File not found"}), 404
    file_path = f"{FILES_DIR}/{file_id}.data"
    if not os.path.exists(file_path):
        return jsonify({"error": "File data missing"}), 404
    return send_file(file_path, as_attachment=True, download_name=meta["filename"])

@app.route("/file/<file_id>/meta", methods=["GET"])
def get_file_meta(file_id):
    meta = get_file_metadata(file_id)
    if not meta:
        return jsonify({"error": "File not found"}), 404
    return jsonify(meta)

@app.route("/delete/<file_id>", methods=["DELETE"])
def delete_file(file_id):
    meta = get_file_metadata(file_id)
    if not meta:
        return jsonify({"error": "File not found"}), 404
    data_path = f"{FILES_DIR}/{file_id}.data"
    meta_path = f"{FILES_DIR}/{file_id}.meta.json"
    if os.path.exists(data_path):
        os.remove(data_path)
    if os.path.exists(meta_path):
        os.remove(meta_path)
    return jsonify({"ok": True, "deleted": file_id})

# ===== CONTROL CHANNEL =====
@app.route("/api/state", methods=["GET", "POST"])
def state():
    if request.method == "GET":
        return jsonify(load(STATE_FILE, {}))
    data = request.get_json(silent=True) or {}
    data["updated"] = datetime.utcnow().isoformat() + "Z"
    save(STATE_FILE, data)
    return jsonify({"ok": True, "state": data})

@app.route("/api/commands", methods=["GET", "POST"])
def commands():
    if request.method == "GET":
        cmds = load(CMD_FILE, [])
        save(CMD_FILE, [])
        return jsonify(cmds)
    data = request.get_json(silent=True) or {}
    cmds = load(CMD_FILE, [])
    cmds.append(data)
    save(CMD_FILE, cmds)
    return jsonify({"ok": True, "queued": len(cmds)})

if __name__ == "__main__":
    app.run()

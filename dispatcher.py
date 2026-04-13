#!/usr/bin/env python3
"""
NULLCLAW Dispatcher Bot
Crew job dispatch bot for Telegram with Claude AI integration.

Commands:
  /new <service> "<name>" "<destination>" <amount>  - Post a new job (or describe it naturally)
  /complete <JOB_ID>                                - Mark job complete
  /stats                                            - Show earnings & stats
  /list                                             - Show pending jobs
  /ask <question>                                   - Ask Claude anything
  /help                                             - Show help

Endpoints:
  POST /webhook/<token>   - Telegram webhook
  POST /deploy            - GitHub Actions auto-deploy (requires DEPLOY_SECRET)
  GET  /health            - Health check
"""

import os
import json
import time
import shlex
import logging
import subprocess
import requests
from flask import Flask, request, jsonify
from datetime import datetime

try:
    import anthropic
    CLAUDE_AVAILABLE = True
except ImportError:
    CLAUDE_AVAILABLE = False

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
CREW_CHAT_ID = os.environ.get('CREW_CHAT_ID', '')
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')
DEPLOY_SECRET = os.environ.get('DEPLOY_SECRET', '')

BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
JOBS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'jobs.json')
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
WSGI_FILE = os.environ.get(
    'WSGI_FILE',
    '/var/www/peakbot_pythonanywhere_com_wsgi.py'
)

app = Flask(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# Claude client (lazy init)
_claude = None

def get_claude():
    global _claude
    if _claude is None and CLAUDE_AVAILABLE and ANTHROPIC_API_KEY:
        _claude = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    return _claude


# ---------------------------------------------------------------------------
# Job persistence
# ---------------------------------------------------------------------------
def load_jobs():
    if os.path.exists(JOBS_FILE):
        with open(JOBS_FILE, 'r') as f:
            return json.load(f)
    return {}


def save_jobs(jobs):
    with open(JOBS_FILE, 'w') as f:
        json.dump(jobs, f, indent=2)


def generate_job_id():
    return f"JOB_{str(int(time.time() * 1000))[-6:]}"


# ---------------------------------------------------------------------------
# Claude AI helpers
# ---------------------------------------------------------------------------
def parse_job_with_claude(text):
    """
    Use Claude to extract structured job data from natural language.
    Returns dict with keys: service, driver, destination, amount
    or None if parsing fails.
    """
    claude = get_claude()
    if not claude:
        return None
    try:
        msg = claude.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=256,
            system="You are a dispatcher assistant. Extract job details from text.",
            messages=[{
                "role": "user",
                "content": (
                    f"Extract job details from this text and return ONLY valid JSON "
                    f"with keys: service, driver, destination, amount (number).\n"
                    f"Text: {text}\n"
                    f'Example: {{"service": "uber", "driver": "Sarah", "destination": "Airport", "amount": 85}}'
                )
            }]
        )
        raw = msg.content[0].text.strip()
        # Strip markdown code fences if present
        if raw.startswith('```'):
            raw = raw.split('```')[1]
            if raw.startswith('json'):
                raw = raw[4:]
        return json.loads(raw.strip())
    except Exception as e:
        logger.error(f"Claude parse error: {e}")
        return None


def ask_claude(question):
    """General Q&A via Claude."""
    claude = get_claude()
    if not claude:
        return "Claude API not configured. Set ANTHROPIC_API_KEY."
    try:
        msg = claude.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            system=(
                "You are NULLCLAW, a smart dispatch assistant for a ride/delivery crew. "
                "Be concise and practical. You help with job coordination, pricing, "
                "routing, and crew management questions."
            ),
            messages=[{"role": "user", "content": question}]
        )
        return msg.content[0].text.strip()
    except Exception as e:
        logger.error(f"Claude ask error: {e}")
        return f"Claude error: {e}"


# ---------------------------------------------------------------------------
# Telegram helpers
# ---------------------------------------------------------------------------
def send_message(chat_id, text, parse_mode='Markdown'):
    url = f"{BASE_URL}/sendMessage"
    payload = {'chat_id': chat_id, 'text': text, 'parse_mode': parse_mode}
    try:
        resp = requests.post(url, json=payload, timeout=10)
        return resp.json()
    except Exception as e:
        logger.error(f"send_message error: {e}")
        return {}


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------
def handle_new_job(message, args_text):
    """
    /new <service> \"<name>\" \"<destination>\" <amount>
    Falls back to Claude for natural language if strict parse fails.
    """
    chat_id = message['chat']['id']
    user = message['from'].get('username') or message['from'].get('first_name', 'Unknown')

    parsed = None

    # Try strict parse first
    try:
        parts = shlex.split(args_text)
        if len(parts) >= 4:
            parsed = {
                'service': parts[0],
                'driver': parts[1],
                'destination': parts[2],
                'amount': float(parts[3]),
            }
    except Exception:
        pass

    # Fall back to Claude if strict parse failed
    if not parsed and args_text.strip():
        send_message(chat_id, "\U0001f9e0 Parsing with Claude...")
        parsed = parse_job_with_claude(args_text)

    if not parsed:
        send_message(
            chat_id,
            "\u274c *Usage:* `/new <service> \"<name>\" \"<destination>\" <amount>`\n"
            "Example: `/new uber \"Sarah\" \"Airport\" 85`\n\n"
            "Or describe naturally: `/new uber job for Sarah going to the airport, $85`"
        )
        return

    jobs = load_jobs()
    job_id = generate_job_id()
    jobs[job_id] = {
        'id': job_id,
        'service': parsed['service'],
        'driver': parsed['driver'],
        'destination': parsed['destination'],
        'amount': float(parsed['amount']),
        'status': 'pending',
        'created_at': datetime.utcnow().isoformat(),
        'created_by': user,
        'completed_at': None,
        'completed_by': None,
    }
    save_jobs(jobs)

    msg = (
        f"\U0001f680 *NEW JOB POSTED*\n"
        f"\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
        f"\U0001f194 `{job_id}`\n"
        f"\U0001f697 Service: *{parsed['service'].upper()}*\n"
        f"\U0001f464 Driver: *{parsed['driver']}*\n"
        f"\U0001f4cd Destination: *{parsed['destination']}*\n"
        f"\U0001f4b0 Amount: *${float(parsed['amount']):.2f}*\n"
        f"\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
        f"To complete: `/complete {job_id}`"
    )
    send_message(chat_id, msg)
    logger.info(f"New job {job_id} created by {user}")


def handle_complete(message, args_text):
    chat_id = message['chat']['id']
    user = message['from'].get('username') or message['from'].get('first_name', 'Unknown')
    job_id = args_text.strip().upper()

    if not job_id:
        send_message(chat_id, "\u274c *Usage:* `/complete JOB_xxx`")
        return

    jobs = load_jobs()

    if job_id not in jobs:
        send_message(chat_id, f"\u274c Job `{job_id}` not found.")
        return

    job = jobs[job_id]
    if job['status'] == 'completed':
        send_message(chat_id, f"\u26a0\ufe0f Job `{job_id}` is already completed.")
        return

    jobs[job_id]['status'] = 'completed'
    jobs[job_id]['completed_at'] = datetime.utcnow().isoformat()
    jobs[job_id]['completed_by'] = user
    save_jobs(jobs)

    msg = (
        f"\u2705 *JOB COMPLETED*\n"
        f"\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
        f"\U0001f194 `{job_id}`\n"
        f"\U0001f697 Service: *{job['service'].upper()}*\n"
        f"\U0001f464 Driver: *{job['driver']}*\n"
        f"\U0001f4cd Destination: *{job['destination']}*\n"
        f"\U0001f4b0 Amount: *${job['amount']:.2f}*\n"
        f"\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
        f"Completed by: @{user}"
    )
    send_message(chat_id, msg)
    logger.info(f"Job {job_id} completed by {user}")


def handle_stats(message):
    chat_id = message['chat']['id']
    jobs = load_jobs()

    if not jobs:
        send_message(chat_id, "\U0001f4ca No jobs posted yet.")
        return

    total = len(jobs)
    completed = sum(1 for j in jobs.values() if j['status'] == 'completed')
    pending = total - completed
    total_earnings = sum(j['amount'] for j in jobs.values() if j['status'] == 'completed')

    services = {}
    for job in jobs.values():
        svc = job['service'].upper()
        services[svc] = services.get(svc, 0) + 1

    service_lines = "\n".join(f"  \u2022 {svc}: {count}" for svc, count in sorted(services.items()))

    msg = (
        f"\U0001f4ca *NULLCLAW STATS*\n"
        f"\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
        f"\U0001f4cb Total Jobs: *{total}*\n"
        f"\u2705 Completed: *{completed}*\n"
        f"\u23f3 Pending: *{pending}*\n"
        f"\U0001f4b0 Total Earnings: *${total_earnings:.2f}*\n"
        f"\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
        f"*By Service:*\n{service_lines}"
    )
    send_message(chat_id, msg)


def handle_list(message):
    chat_id = message['chat']['id']
    jobs = load_jobs()
    pending = {jid: j for jid, j in jobs.items() if j['status'] == 'pending'}

    if not pending:
        send_message(chat_id, "\U0001f4cb No pending jobs.")
        return

    lines = [f"\U0001f4cb *PENDING JOBS ({len(pending)})*\n\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501"]
    for jid, job in list(pending.items())[-10:]:
        lines.append(
            f"`{jid}` \U0001f697 {job['service'].upper()} "
            f"\U0001f464 {job['driver']} \U0001f4cd {job['destination']} "
            f"\U0001f4b0 ${job['amount']:.2f}"
        )
    send_message(chat_id, "\n".join(lines))


def handle_ask(message, args_text):
    """Handle /ask <question> - powered by Claude"""
    chat_id = message['chat']['id']
    question = args_text.strip()

    if not question:
        send_message(chat_id, "\u274c *Usage:* `/ask <your question>`")
        return

    send_message(chat_id, "\U0001f9e0 Thinking...")
    answer = ask_claude(question)
    send_message(chat_id, answer)


def handle_help(message):
    chat_id = message['chat']['id']
    claude_status = "\u2705 Active" if (CLAUDE_AVAILABLE and ANTHROPIC_API_KEY) else "\u274c Not configured"
    msg = (
        "\U0001f916 *NULLCLAW DISPATCHER*\n"
        "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
        "*Commands:*\n"
        "`/new <service> \"<name>\" \"<dest>\" <amount>`\n"
        "  Post a job (natural language OK)\n\n"
        "`/complete <JOB_ID>`\n"
        "  Mark a job as complete\n\n"
        "`/stats`\n"
        "  Show earnings & job stats\n\n"
        "`/list`\n"
        "  Show pending jobs\n\n"
        "`/ask <question>`\n"
        "  Ask Claude anything\n\n"
        "`/help`\n"
        "  Show this message\n"
        "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
        f"\U0001f9e0 Claude AI: {claude_status}\n"
        "*Example:*\n"
        "`/new uber \"Sarah\" \"Airport\" 85`"
    )
    send_message(chat_id, msg)


# ---------------------------------------------------------------------------
# Update dispatcher
# ---------------------------------------------------------------------------
def process_update(update):
    message = update.get('message') or update.get('edited_message')
    if not message:
        return

    text = message.get('text', '')
    if not text.startswith('/'):
        return

    parts = text.split(None, 1)
    command = parts[0].split('@')[0].lower()
    args = parts[1] if len(parts) > 1 else ''

    dispatch = {
        '/new': lambda: handle_new_job(message, args),
        '/complete': lambda: handle_complete(message, args),
        '/stats': lambda: handle_stats(message),
        '/list': lambda: handle_list(message),
        '/ask': lambda: handle_ask(message, args),
        '/help': lambda: handle_help(message),
        '/start': lambda: handle_help(message),
    }

    handler = dispatch.get(command)
    if handler:
        handler()


# ---------------------------------------------------------------------------
# Flask routes
# ---------------------------------------------------------------------------
@app.route('/webhook/<token>', methods=['POST'])
def webhook(token):
    if token != TELEGRAM_BOT_TOKEN:
        return jsonify({'error': 'unauthorized'}), 403
    update = request.get_json(silent=True)
    if update:
        process_update(update)
    return jsonify({'ok': True})


@app.route('/deploy', methods=['POST'])
def deploy():
    """
    Called by GitHub Actions on every push to main.
    Pulls latest code and reloads the WSGI app.
    Protected by DEPLOY_SECRET bearer token.
    """
    if not DEPLOY_SECRET:
        return jsonify({'error': 'DEPLOY_SECRET not configured'}), 500

    auth = request.headers.get('Authorization', '')
    if auth != f'Bearer {DEPLOY_SECRET}':
        logger.warning("Deploy attempt with invalid secret")
        return jsonify({'error': 'unauthorized'}), 403

    try:
        # Pull latest code
        pull = subprocess.run(
            ['git', 'pull'],
            cwd=PROJECT_DIR,
            capture_output=True,
            text=True,
            timeout=30
        )
        logger.info(f"git pull: {pull.stdout.strip()}")

        # Touch WSGI file to trigger PythonAnywhere reload
        if os.path.exists(WSGI_FILE):
            os.utime(WSGI_FILE, None)
            logger.info(f"Touched {WSGI_FILE} to trigger reload")
        else:
            logger.warning(f"WSGI file not found at {WSGI_FILE} — reload may not trigger")

        return jsonify({
            'status': 'ok',
            'git': pull.stdout.strip() or pull.stderr.strip(),
        })
    except Exception as e:
        logger.error(f"Deploy error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'ok',
        'bot': 'NULLCLAW Dispatcher',
        'claude': CLAUDE_AVAILABLE and bool(ANTHROPIC_API_KEY),
    })


@app.route('/', methods=['GET'])
def index():
    return 'NULLCLAW Dispatcher is running.'


# ---------------------------------------------------------------------------
# Webhook management
# ---------------------------------------------------------------------------
def set_webhook(webhook_url):
    resp = requests.post(f"{BASE_URL}/setWebhook", json={'url': webhook_url}, timeout=10)
    return resp.json()


def delete_webhook():
    resp = requests.post(f"{BASE_URL}/deleteWebhook", timeout=10)
    return resp.json()


# ---------------------------------------------------------------------------
# Long-polling mode (local testing)
# ---------------------------------------------------------------------------
def run_polling():
    logger.info("Long-polling mode — deleting webhook first...")
    delete_webhook()
    offset = None
    while True:
        params = {'timeout': 30}
        if offset is not None:
            params['offset'] = offset
        try:
            resp = requests.get(f"{BASE_URL}/getUpdates", params=params, timeout=35)
            data = resp.json()
            if data.get('ok'):
                for update in data.get('result', []):
                    process_update(update)
                    offset = update['update_id'] + 1
        except Exception as e:
            logger.error(f"Polling error: {e}")
            time.sleep(5)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    import sys

    if not TELEGRAM_BOT_TOKEN:
        print("ERROR: TELEGRAM_BOT_TOKEN not set")
        sys.exit(1)

    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == 'polling':
            run_polling()
        elif cmd == 'setwebhook' and len(sys.argv) > 2:
            print(set_webhook(sys.argv[2]))
        elif cmd == 'deletewebhook':
            print(delete_webhook())
        else:
            print(f"Usage: python dispatcher.py [polling | setwebhook <url> | deletewebhook]")
    else:
        port = int(os.environ.get('PORT', 5000))
        app.run(host='0.0.0.0', port=port, debug=False)

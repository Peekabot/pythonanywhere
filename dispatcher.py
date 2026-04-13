#!/usr/bin/env python3
"""
NULLCLAW Dispatcher Bot
Crew job dispatch bot for Telegram

Commands:
  /new <service> "<name>" "<destination>" <amount>  - Post a new job
  /complete <JOB_ID>                                - Mark job complete
  /stats                                            - Show earnings & stats
  /list                                             - Show pending jobs
  /help                                             - Show help
"""

import os
import json
import time
import shlex
import logging
import requests
from flask import Flask, request, jsonify
from datetime import datetime

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
CREW_CHAT_ID = os.environ.get('CREW_CHAT_ID', '')
BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
JOBS_FILE = os.path.join(os.path.dirname(__file__), 'jobs.json')

app = Flask(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


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
    # Last 6 digits of millisecond timestamp
    return f"JOB_{str(int(time.time() * 1000))[-6:]}"


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
    """Handle /new <service> \"<name>\" \"<destination>\" <amount>"""
    chat_id = message['chat']['id']
    user = message['from'].get('username') or message['from'].get('first_name', 'Unknown')

    try:
        parts = shlex.split(args_text)
        if len(parts) < 4:
            raise ValueError("Not enough arguments")
        service = parts[0]
        driver_name = parts[1]
        destination = parts[2]
        amount = float(parts[3])
    except Exception:
        send_message(
            chat_id,
            "\u274c *Usage:* `/new <service> \"<name>\" \"<destination>\" <amount>`\n"
            "Example: `/new uber \"Sarah\" \"Airport\" 85`"
        )
        return

    jobs = load_jobs()
    job_id = generate_job_id()
    jobs[job_id] = {
        'id': job_id,
        'service': service,
        'driver': driver_name,
        'destination': destination,
        'amount': amount,
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
        f"\U0001f697 Service: *{service.upper()}*\n"
        f"\U0001f464 Driver: *{driver_name}*\n"
        f"\U0001f4cd Destination: *{destination}*\n"
        f"\U0001f4b0 Amount: *${amount:.2f}*\n"
        f"\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
        f"To complete: `/complete {job_id}`"
    )
    send_message(chat_id, msg)
    logger.info(f"New job {job_id} created by {user}")


def handle_complete(message, args_text):
    """Handle /complete <JOB_ID>"""
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
    """Handle /stats"""
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
    """Handle /list — show last 10 pending jobs"""
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


def handle_help(message):
    """Handle /help and /start"""
    chat_id = message['chat']['id']
    msg = (
        "\U0001f916 *NULLCLAW DISPATCHER*\n"
        "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
        "*Commands:*\n"
        "`/new <service> \"<name>\" \"<dest>\" <amount>`\n"
        "  Post a new job\n\n"
        "`/complete <JOB_ID>`\n"
        "  Mark a job as complete\n\n"
        "`/stats`\n"
        "  Show earnings & job stats\n\n"
        "`/list`\n"
        "  Show pending jobs\n\n"
        "`/help`\n"
        "  Show this message\n"
        "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
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
    command = parts[0].split('@')[0].lower()  # handle /cmd@botname
    args = parts[1] if len(parts) > 1 else ''

    dispatch = {
        '/new': lambda: handle_new_job(message, args),
        '/complete': lambda: handle_complete(message, args),
        '/stats': lambda: handle_stats(message),
        '/list': lambda: handle_list(message),
        '/help': lambda: handle_help(message),
        '/start': lambda: handle_help(message),
    }

    handler = dispatch.get(command)
    if handler:
        handler()
    else:
        logger.debug(f"Unknown command: {command}")


# ---------------------------------------------------------------------------
# Flask routes (webhook mode)
# ---------------------------------------------------------------------------
@app.route('/webhook/<token>', methods=['POST'])
def webhook(token):
    if token != TELEGRAM_BOT_TOKEN:
        return jsonify({'error': 'unauthorized'}), 403
    update = request.get_json(silent=True)
    if update:
        process_update(update)
    return jsonify({'ok': True})


@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'bot': 'NULLCLAW Dispatcher'})


@app.route('/', methods=['GET'])
def index():
    return 'NULLCLAW Dispatcher is running.'


# ---------------------------------------------------------------------------
# Webhook management helpers
# ---------------------------------------------------------------------------
def set_webhook(webhook_url):
    resp = requests.post(f"{BASE_URL}/setWebhook", json={'url': webhook_url}, timeout=10)
    return resp.json()


def delete_webhook():
    resp = requests.post(f"{BASE_URL}/deleteWebhook", timeout=10)
    return resp.json()


# ---------------------------------------------------------------------------
# Long-polling mode (for local testing)
# ---------------------------------------------------------------------------
def run_polling():
    logger.info("Starting long-polling mode (delete webhook first)...")
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
        print("ERROR: TELEGRAM_BOT_TOKEN environment variable not set.")
        sys.exit(1)

    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == 'polling':
            run_polling()
        elif cmd == 'setwebhook' and len(sys.argv) > 2:
            result = set_webhook(sys.argv[2])
            print(f"Webhook result: {result}")
        elif cmd == 'deletewebhook':
            result = delete_webhook()
            print(f"Delete webhook result: {result}")
        else:
            print(f"Unknown command: {cmd}")
            print("Usage: python dispatcher.py [polling | setwebhook <url> | deletewebhook]")
    else:
        # Run Flask dev server (webhook mode)
        port = int(os.environ.get('PORT', 5000))
        app.run(host='0.0.0.0', port=port, debug=False)

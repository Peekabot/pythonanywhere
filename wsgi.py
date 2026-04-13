"""
PythonAnywhere WSGI entry point.

In the PythonAnywhere Web tab:
  Source code:  /home/<username>/pythonanywhere
  Working dir:  /home/<username>/pythonanywhere
  WSGI file:    this file (or point to it)
  Virtualenv:   /home/<username>/.virtualenvs/crewbot-env

Set TELEGRAM_BOT_TOKEN and CREW_CHAT_ID in the
'Environment variables' section of the Web tab (or in a .env file).
"""

import sys
import os

# Add project directory to path
project_home = os.path.dirname(os.path.abspath(__file__))
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# Load .env file if present (optional - prefer Web tab env vars)
_env_file = os.path.join(project_home, '.env')
if os.path.exists(_env_file):
    with open(_env_file) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith('#') and '=' in _line:
                _key, _val = _line.split('=', 1)
                os.environ.setdefault(_key.strip(), _val.strip().strip("'\""))

from dispatcher import app as application  # noqa: E402

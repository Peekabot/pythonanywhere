# Peekagate capabilities

Public API: `https://peekabot.pythonanywhere.com`

## Endpoints
| Method | Path | Role |
|--------|------|------|
| GET/POST | `/api/state` | Read or replace JSON state |
| GET/POST | `/api/commands` | Pull (clears) or queue commands |
| GET | `/` | Operator dashboard |
| POST | `/upload` | File upload |
| GET | `/list` | List uploads |

**State is full replace** on POST. Workers use a `LAST` dict so results survive heartbeats.

## Commands

Always send JSON header:
```bash
curl -sS -X POST https://peekabot.pythonanywhere.com/api/commands \
  -H "Content-Type: application/json" \
  -d '{"action":"ping"}'
```

Optional `"target": "pythonista" | "ish" | "all"`. Workers should skip jobs not for them.

| action | Pythonista | iSH | Body fields |
|--------|------------|-----|-------------|
| `ping` | yes | yes | |
| `hw` / `hardware` | yes | yes | |
| `echo` | yes | yes | `message` |
| `ls` / `list` | yes | yes | `path` |
| `read` | yes | yes | `path` |
| `scripts` | **yes** | optional | |
| `search` | **yes** | optional | `q` |
| `notify` | **yes** | no | `message` |
| `upload` | **yes** | no | `path`, `tag` |
| `open_url` | **yes** | no | `url` |
| `run` | no | **yes** | `cmd` |
| `bagster_set` | planned | planned | `status`, `zip`, `notes`, `pickup_usd` |

## Read results
```bash
curl -sS https://peekabot.pythonanywhere.com/api/state
```
Wait ~15–45s after queue for a worker poll.

## Operator vs customer
- **Operator:** this API + workers (iSH / Pythonista / Termux)
- **Customer:** static site only (e.g. GitHub Pages) — no command API

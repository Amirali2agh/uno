 🃏 UNO Game Server (Real-Time Multiplayer)

A highly scalable, real-time multiplayer UNO game server built with **FastAPI**, **WebSockets**, and **Redis**. Designed with Clean Architecture, Modular Design, and robust concurrency management.

## ✨ Features

- **Real-Time Gameplay:** Low-latency bidirectional communication using WebSockets.
- **Smart Matchmaking:** Automated queue system for 2-player and 4-player game modes.
- **UNO Rules:** Skip, Reverse, Draw 2, Wild, Wild 4 (with the "no matching colour" restriction),
  draw-then-play turns, the starting-card effect, and the UNO call/challenge penalty — all validated on the server side.
- **Concurrency Control:** Redis distributed locks with a bounded wait around every game mutation.
- **Fault Tolerance:** configurable disconnect grace period (`DISCONNECT_TIMEOUT_SECONDS`). If a player drops, the game waits; if they do not return in time, the opponent wins (a larger game is abandoned).
- **Dockerized:** Ready for production deployment.

## 🛠️ Tech Stack

- **Backend Framework:** FastAPI (Python 3.12+)
- **Real-Time Communication:** WebSockets
- **State Store:** Redis (asyncio), game state serialised with a TTL
- **Data Validation:** Pydantic V2
- **Testing:** Pytest & Pytest-Asyncio
- **Containerization:** Docker

## 📂 Project Architecture

```text
uno-game/
├── app/
│   ├── api/
│   │   └── websockets/      # WebSocket endpoints (queue.py, room.py)
│   ├── managers/            # In-memory connection managers
│   ├── routers/             # RESTful endpoints (admin.py)
│   ├── services/            # Core business logic (game_service, queue_service)
│   ├── utils/               # Helpers (redis_keys.py)
│   ├── config.py            # Environment variables & settings
│   ├── main.py              # FastAPI application entry point
│   └── redis_client.py      # Async Redis connection pool
├── tests/                   # Automated test suite
├── Dockerfile               # Docker configuration
├── pytest.ini               # Pytest configuration
└── requirements.txt         # Python dependencies
🚀 Getting Started
Prerequisites
Python 3.12 or higher
Redis Server (running on localhost:6379 by default)
1. Installation
Clone the repository and set up a virtual environment:
code
Bash
python3 -m venv .venv
source .venv/bin/activate
Install dependencies (Using Chabokan mirror for faster access in restricted regions):
code
Bash
pip install --index-url https://mirror2.chabokan.net/pypi/simple/ -r requirements.txt
2. Running the Server
Start the FastAPI server using Uvicorn:
code
Bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
The server will be available at http://localhost:8000.
3. Running Tests
The project includes a test suite. Install the dev dependencies once, then run it
against a reachable Redis server:

```bash
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest -v
```

Tests use a separate Redis database (default `15`, override with `TEST_REDIS_URL`)
and are flushed around every test, so they never interfere with a running server.
4. Running the Frontend (development)
The React client lives in `front/`. Start the Vite dev server in a second terminal:

```bash
cd front
npm install
npm run dev            # http://localhost:5173
```

The dev server proxies `/ws` and `/admin` to the backend (`http://127.0.0.1:8000`
by default, override with the `BACKEND_ORIGIN` environment variable), so the
browser always talks to a single origin and no CORS configuration is needed.

The client identifies the player through query parameters, e.g.
`http://localhost:5173/?player_id=42&player_name=Ali&player_avatar=/avatars/42.jpg`.

🔌 WebSocket Endpoints
1. Matchmaking Queue
ws://<host>:<port>/ws/queue/{player_count}?player_id={your_id}
player_count: 2 or 4
Behavior: Puts the player in the queue. Once enough players join, the server sends a match_found event with a game_id.
2. Game Room
ws://<host>:<port>/ws/room/{game_id}?player_id={your_id}
Behavior: Connects the player to the active game.
Actions (Client -> Server):
Draw a card: {"action": "draw_card"}
Play a card: {"action": "play_card", "card_index": 1, "chosen_color": "red"}
Pass the turn after drawing: {"action": "pass_turn"}
Announce UNO: {"action": "say_uno"}
Challenge a missed UNO: {"action": "challenge_uno"}
Play and announce UNO together: {"action": "play_card", "card_index": 0, "say_uno": true}

Every rejected action answers with a structured error and the socket stays open:

```json
{"type": "error", "code": "not_your_turn", "message": "It is not your turn."}
```

Reason codes: `invalid_json`, `invalid_message`, `invalid_action`, `message_too_large`,
`internal_error`, `game_not_found`, `game_finished`, `not_your_turn`, `card_not_in_hand`,
`must_play_drawn_card`, `invalid_card`, `color_required`, `invalid_color`,
`wild4_has_matching_color`, `already_drawn`, `nothing_to_pass`, `cannot_call_uno`,
`nothing_to_challenge`.
🛠️ Admin Endpoint
`GET /admin/stats` returns queue lengths (global, from Redis) and connection/room
counters (per process). It is disabled until `ADMIN_TOKEN` is set:

```bash
export ADMIN_TOKEN=change-me
curl -H "X-Admin-Token: change-me" http://localhost:8000/admin/stats
```

🐳 Docker Deployment
The image is built from a filtered context (`.dockerignore`): no `front/`, no
`node_modules`, no tests, no `.git`. It runs as an unprivileged user (`appuser`,
uid 10001) and ships a `HEALTHCHECK` that probes `/`.

Build the Docker image:

```bash
docker build -t uno-game-server .
```

Run the container (ensure a Redis container is also running and accessible):

```bash
docker run -d -p 8000:8000 -e REDIS_URL=redis://<redis-host>:6379/0 uno-game-server
```

Or bring up both services (Redis waits for its healthcheck, the backend then
starts and exposes its own health status):

```bash
docker compose up --build
```

### Scaling note
Room and queue connection registries live in the process memory, so the app must
run with a **single uvicorn worker** (or sticky routing per game). Redis holds the
authoritative game state, but live WebSocket fan-out is local to the process. The
`/admin/stats` counters are labelled `process:<pid>` for that reason.
Developed with ❤️ focusing on Clean Code and Scalability.
code
Code
---

### توضیحات:
این فایل `README.md` شامل بخش‌های زیر است:
۱. **معرفی و ویژگی‌ها (Features):** تمام قابلیت‌های خفنی که پیاده کردیم (مثل قفل‌های ردیس، تایم‌اوت ۶۰ ثانیه و مچ‌میکینگ) را لیست کرده است.
۲. **تکنولوژی‌ها (Tech Stack):** ابزارهای استفاده شده را مشخص می‌کند.
۳. **ساختار پروژه (Architecture):** به برنامه‌نویسان دیگر نشان می‌دهد که معماری ما چقدر تمیز و ماژولار است.
۴. **نحوه اجرا و تست (Getting Started):** دستورات دقیق برای نصب (با میرور چابکان)، اجرای سرور و اجرای تست‌ها.
۵. **مستندات API (Endpoints):** نحوه اتصال به وب‌سوکت‌ها و فرمت پیام‌ها را برای فرانت‌اند کارها توضیح می‌دهد.
۶. **داکر (Docker):** دستورات ساخت و اجرای کانتینر.

پروژه بک‌اند شما اکنون یک پکیج کامل، حرفه‌ای و آماده ارائه (Production-ready) است. 
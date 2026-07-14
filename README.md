 🃏 UNO Game Server (Real-Time Multiplayer)

A highly scalable, real-time multiplayer UNO game server built with **FastAPI**, **WebSockets**, and **Redis**. Designed with Clean Architecture, Modular Design, and robust concurrency management.

## ✨ Features

- **Real-Time Gameplay:** Low-latency bidirectional communication using WebSockets.
- **Smart Matchmaking:** Automated queue system for 2-player and 4-player game modes.
- **Robust Game Logic:** Full UNO rules implementation (Skip, Reverse, Draw 2, Wild, Wild 4) validated on the server side.
- **Concurrency Control:** Utilizes Redis Distributed Locks (Redlock) to prevent race conditions during simultaneous card plays.
- **Fault Tolerance:** 60-second automated disconnect timeout. If a player drops, the game waits; if they don't return, the opponent wins.
- **Dockerized:** Ready for production deployment.

## 🛠️ Tech Stack

- **Backend Framework:** FastAPI (Python 3.12+)
- **Real-Time Communication:** WebSockets
- **In-Memory Database & Pub/Sub:** Redis (asyncio)
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
The project includes a comprehensive test suite. To run the tests:
code
Bash
python -m pytest -v
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
🐳 Docker Deployment
Build the Docker image:
code
Bash
docker build -t uno-game-server .
Run the container (Ensure a Redis container is also running and accessible):
code
Bash
docker run -d -p 8000:8000 uno-game-server
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
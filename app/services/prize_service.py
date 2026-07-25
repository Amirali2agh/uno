import os
import httpx

PORTEGHAL_API_URL = os.getenv("PORTEGHAL_API_URL", "http://localhost:8090")
PORTEGHAL_API_KEY = os.getenv("PORTEGHAL_API_KEY", "t1rrI33VfJDbopVF9vfOjBVgtaKJb7P4XzQ37BQkqvw=")
WINNER_ENDPOINT = f"{PORTEGHAL_API_URL}/api/internal/game-winner"


async def update_room_status(room_id: str, status: str) -> bool:
    """Update room status in porteghal's game_rooms collection."""
    url = f"{PORTEGHAL_API_URL}/api/internal/game-rooms/update"
    headers = {"Content-Type": "application/json", "X-Api-Key": PORTEGHAL_API_KEY}
    payload = {"roomId": room_id, "status": status}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return True
    except (httpx.HTTPError, httpx.RequestError) as exc:
        print(f"❌ Failed to update room {room_id} status: {exc}")
        return False


async def report_winner(
    room_id: str,
    player_id: str,
    win_type: str,
    game_id: str = "uno",
    amount: int = 0,
) -> bool:
    """Report a game winner to the Porteghal internal API."""
    payload = {
        "player_id": player_id,
        "amount": amount,
        "room_id": room_id,
        "win_type": win_type,
        "game_id": game_id,
    }
    headers = {"Content-Type": "application/json", "X-Api-Key": PORTEGHAL_API_KEY}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(WINNER_ENDPOINT, json=payload, headers=headers)
            response.raise_for_status()
            return True
    except (httpx.HTTPError, httpx.RequestError) as exc:
        print(f"❌ Failed to report winner: {exc}")
        return False

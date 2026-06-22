# Base prefix to isolate our game keys from other keys in Redis
BASE_PREFIX = "uno"

def get_queue_key(player_count: int) -> str:
    """
    Generate the key for the matchmaking queue based on player count (e.g., 2 or 4).
    Example: uno:queue:2
    """
    return f"{BASE_PREFIX}:queue:{player_count}"

def get_game_state_key(game_id: str) -> str:
    """
    Generate the key for storing the active game state JSON.
    Example: uno:game:abc-123:state
    """
    return f"{BASE_PREFIX}:game:{game_id}:state"

def get_game_lock_key(game_id: str) -> str:
    """
    Generate the key for the Distributed Lock (Redlock) of a game room.
    Example: uno:lock:game:abc-123
    """
    return f"{BASE_PREFIX}:lock:game:{game_id}"

def get_player_disconnect_key(player_id: str) -> str:
    """
    Generate the key used to trigger the 60-second disconnect timeout.
    Example: uno:player:player-99:disconnect
    """
    return f"{BASE_PREFIX}:player:{player_id}:disconnect"
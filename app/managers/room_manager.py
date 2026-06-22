import asyncio
from fastapi import WebSocket
from redis.asyncio import Redis
from app.utils.redis_keys import get_player_disconnect_key
from app.services.game_service import GameService

class RoomManager:
    def __init__(self, timeout_seconds: int = 60):
        # Format: {game_id: {player_id: WebSocket}}
        self.rooms: dict[str, dict[str, WebSocket]] = {}
        self.timeout_seconds = timeout_seconds

    async def connect(self, game_id: str, player_id: str, websocket: WebSocket, redis: Redis):
        """Accepts connection and registers the player in their game room."""
        await websocket.accept()
        
        if game_id not in self.rooms:
            self.rooms[game_id] = {}
        self.rooms[game_id][player_id] = websocket

        # If player reconnected, delete their Redis disconnect key to cancel the timeout
        disconnect_key = get_player_disconnect_key(player_id)
        await redis.delete(disconnect_key)

    async def disconnect(self, game_id: str, player_id: str, redis: Redis):
        """Removes player from room and starts a background task for disconnect timeout."""
        if game_id in self.rooms and player_id in self.rooms[game_id]:
            del self.rooms[game_id][player_id]
            # Remove room entry if it is completely empty
            if not self.rooms[game_id]:
                del self.rooms[game_id]

        # Start a non-blocking background task to wait for reconnection
        asyncio.create_task(self._start_disconnect_timeout(game_id, player_id, redis))

    async def _start_disconnect_timeout(self, game_id: str, player_id: str, redis: Redis):
        """Sets an expiration key in Redis and checks after timeout if player is still offline."""
        disconnect_key = get_player_disconnect_key(player_id)
        
        # Use simple and clean integer EXPIRE
        await redis.set(disconnect_key, "disconnected", ex=int(self.timeout_seconds))
        
        # Wait for the specified timeout duration
        await asyncio.sleep(self.timeout_seconds)
        
        # Check in-memory connections to see if player has reconnected
        is_reconnected = (game_id in self.rooms) and (player_id in self.rooms[game_id])
        
        if not is_reconnected:
            # Cleanup Redis key manually
            await redis.delete(disconnect_key)
            
            # Game over: Player failed to reconnect in time
            game_service = GameService(redis)
            state = await game_service.get_game_state(game_id)
            if state and state.status == "active":
                state.status = "finished"
                state.winner = f"Opponent (Player {player_id} disconnected)"
                await game_service.save_game_state(state)
                
                # Notify remaining players in the room
                await self.broadcast(game_id, {
                    "type": "game_over",
                    "reason": f"Player {player_id} was disconnected for more than {self.timeout_seconds}s.",
                    "state": state.model_dump()
                })

    async def broadcast(self, game_id: str, message: dict):
        """Sends a JSON message to all connected players in the game room."""
        if game_id in self.rooms:
            for player_id, websocket in self.rooms[game_id].items():
                try:
                    await websocket.send_json(message)
                except Exception:
                    pass

# Instantiate global manager
room_manager = RoomManager()

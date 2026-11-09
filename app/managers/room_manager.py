import os
import asyncio
import logging
import math

from fastapi import WebSocket
from redis.asyncio import Redis
from app.config import settings
from app.utils.redis_keys import get_player_disconnect_key
from app.services.game_service import GameService, GameState

logger = logging.getLogger(__name__)

class RoomManager:
    def __init__(self, timeout_seconds: int = 60):
        # Identifies this worker in admin stats (counters are per process).
        self.process_id = os.getpid()
        # Format: {game_id: {player_id: WebSocket}}
        self.rooms: dict[str, dict[str, WebSocket]] = {}
        self.timeout_seconds = timeout_seconds
        # Timers are kept here: asyncio only holds weak references to tasks, so a
        # fire-and-forget task can be garbage collected before it fires.
        self._timeout_tasks: dict[tuple[str, str], asyncio.Task] = {}

    def _cancel_timeout_task(self, game_id: str, player_id: str) -> None:
        """Stop the pending disconnect timer for a seat (reconnect or re-disconnect)."""
        task = self._timeout_tasks.pop((game_id, player_id), None)
        if task is not None and not task.done():
            task.cancel()

    def _start_timeout_task(self, game_id: str, player_id: str, redis: Redis) -> None:
        key = (game_id, player_id)
        self._cancel_timeout_task(game_id, player_id)
        task = asyncio.create_task(self._start_disconnect_timeout(game_id, player_id, redis))
        self._timeout_tasks[key] = task

        def _discard(finished: asyncio.Task) -> None:
            # Only drop the entry if it still points at this task.
            if self._timeout_tasks.get(key) is finished:
                self._timeout_tasks.pop(key, None)

        task.add_done_callback(_discard)

    async def connect(self, game_id: str, player_id: str, websocket: WebSocket, redis: Redis):
        """Accepts connection and registers the player in their game room."""
        await websocket.accept()
        
        if game_id not in self.rooms:
            self.rooms[game_id] = {}
        self.rooms[game_id][player_id] = websocket

        # If player reconnected, cancel the pending timer and delete their Redis key
        self._cancel_timeout_task(game_id, player_id)
        disconnect_key = get_player_disconnect_key(player_id)
        await redis.delete(disconnect_key)

    async def disconnect(self, game_id: str, player_id: str, redis: Redis):
        """Removes player from room and starts a background task for disconnect timeout."""
        if game_id in self.rooms and player_id in self.rooms[game_id]:
            del self.rooms[game_id][player_id]
            # Remove room entry if it is completely empty
            if not self.rooms[game_id]:
                del self.rooms[game_id]

        # Start a retained background task to wait for reconnection
        self._start_timeout_task(game_id, player_id, redis)

    async def _start_disconnect_timeout(self, game_id: str, player_id: str, redis: Redis):
        """Sets an expiration key in Redis and checks after timeout if player is still offline."""
        disconnect_key = get_player_disconnect_key(player_id)
        
        # Redis EXPIRE needs whole seconds: sub-second test timeouts round up.
        await redis.set(disconnect_key, "disconnected", ex=max(1, math.ceil(self.timeout_seconds)))
        
        # Wait for the specified timeout duration (cancelled on reconnect)
        try:
            await asyncio.sleep(self.timeout_seconds)
        except asyncio.CancelledError:
            raise
        
        # Check in-memory connections to see if player has reconnected
        is_reconnected = (game_id in self.rooms) and (player_id in self.rooms[game_id])
        
        if not is_reconnected:
            # Cleanup Redis key manually
            try:
                await redis.delete(disconnect_key)
            except Exception:  # pragma: no cover - best effort cleanup
                logger.warning("Could not delete disconnect key for %s", player_id)
            
            # Game over: Player failed to reconnect in time
            game_service = GameService(redis)
            state = await game_service.get_game_state(game_id)
            if state and state.status == "active":
                remaining = [p.player_id for p in state.players if p.player_id != player_id]
                state.status = "finished"
                state.end_reason = "disconnect_timeout"
                state.disconnected_player_id = player_id
                # A two-player game is won by the player who stayed; with more
                # seats the match is abandoned and has no single winner.
                state.winner = remaining[0] if len(remaining) == 1 else None
                await game_service.save_game_state(state)
                
                # Notify remaining players in the room, each with their own view
                await self.broadcast_state(
                    game_id,
                    state,
                    extra={
                        "type": "game_over",
                        "reason": f"Player {player_id} was disconnected for more than {self.timeout_seconds}s.",
                    },
                )

    async def broadcast_state(self, game_id: str, state: GameState, extra: dict | None = None):
        """Send every player their own projection of the game state.

        Hands of other players and the order of the draw pile never leave the
        server (see GameState.for_player).
        """
        for player_id, websocket in list(self.rooms.get(game_id, {}).items()):
            try:
                message = {"type": "state_update", "state": state.for_player(player_id).model_dump()}
                if extra:
                    message.update(extra)
                await websocket.send_json(message)
            except Exception:
                pass

    async def broadcast(self, game_id: str, message: dict):
        """Sends a JSON message to all connected players in the game room."""
        if game_id in self.rooms:
            for player_id, websocket in self.rooms[game_id].items():
                try:
                    await websocket.send_json(message)
                except Exception:
                    pass

# Instantiate the global manager from configuration so DISCONNECT_TIMEOUT_SECONDS
# actually controls the reconnect grace period.
room_manager = RoomManager(timeout_seconds=settings.DISCONNECT_TIMEOUT_SECONDS)

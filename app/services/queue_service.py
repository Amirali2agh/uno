import json
from redis.asyncio import Redis
from app.utils.redis_keys import get_queue_key

class QueueService:
    def __init__(self, redis: Redis):
        # We inject the Redis client instance via constructor (Dependency Injection)
        self.redis = redis

    async def join_queue(self, player_data: dict) -> bool:
        """
        Adds a player to the matchmaking queue.
        player_data: {"player_id": str, "player_name": str, "player_avatar": str}
        To avoid duplicates, we first remove any existing instance of this player in the queue.
        """
        player_id = player_data["player_id"]
        player_count = player_data["player_count"]
        queue_key = get_queue_key(player_count)

        # Remove any existing duplicate entries of this player
        await self._remove_player_from_queue(player_id, player_count)

        # Push structured data to the end of the FIFO queue
        await self.redis.rpush(queue_key, json.dumps(player_data))
        return True

    async def _remove_player_from_queue(self, player_id: str, player_count: int) -> bool:
        """Remove all entries for a given player_id from a queue. Returns True if any were removed."""
        queue_key = get_queue_key(player_count)
        removed = False
        # Scan the queue and remove entries matching this player_id
        queue_length = await self.redis.llen(queue_key)
        for _ in range(queue_length):
            item = await self.redis.lpop(queue_key)
            if item:
                try:
                    entry = json.loads(item)
                    if isinstance(entry, dict) and entry.get("player_id") == player_id:
                        removed = True
                        continue  # skip (effectively removes it)
                except (json.JSONDecodeError, TypeError):
                    pass
                # Re-push everything else
                await self.redis.rpush(queue_key, item)
        return removed

    async def leave_queue(self, player_id: str, player_count: int) -> bool:
        """
        Removes a player from the matchmaking queue when they cancel matchmaking.
        """
        removed = await self._remove_player_from_queue(player_id, player_count)
        return removed

    async def try_match(self, player_count: int) -> list[dict] | None:
        """
        Checks if there are enough players in the queue to start a game.
        If yes, it pops exactly 'player_count' players atomically using a Redis lock.
        Returns list of player data dicts, or None if not enough players.
        """
        queue_key = get_queue_key(player_count)
        lock_key = f"uno:lock:queue:{player_count}"

        # Use Redis Distributed Lock to prevent concurrent matchmaking race conditions
        async with self.redis.lock(lock_key, timeout=5):
            # Check the current number of players waiting in the queue
            current_len = await self.redis.llen(queue_key)

            # If we have enough players, extract them from the queue
            if current_len >= player_count:
                matched_players = []
                for _ in range(player_count):
                    item = await self.redis.lpop(queue_key)
                    if item:
                        try:
                            entry = json.loads(item)
                            if isinstance(entry, dict):
                                matched_players.append(entry)
                        except (json.JSONDecodeError, TypeError):
                            # Legacy plain string player_id — wrap in dict
                            matched_players.append({"player_id": item, "player_name": "", "player_avatar": ""})
                return matched_players if len(matched_players) == player_count else None

        # Return None if there are not enough players
        return None
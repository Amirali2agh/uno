from redis.asyncio import Redis
from app.utils.redis_keys import get_queue_key

class QueueService:
    def __init__(self, redis: Redis):
        # We inject the Redis client instance via constructor (Dependency Injection)
        self.redis = redis

    async def join_queue(self, player_id: str, player_count: int) -> bool:
        """
        Adds a player to the matchmaking queue.
        To avoid duplicates, we first remove any existing instance of this player in the queue.
        """
        queue_key = get_queue_key(player_count)
        
        # Remove any existing duplicate entries of this player
        await self.redis.lrem(queue_key, 0, player_id)
        
        # Push player to the end of the FIFO queue
        await self.redis.rpush(queue_key, player_id)
        return True

    async def leave_queue(self, player_id: str, player_count: int) -> bool:
        """
        Removes a player from the matchmaking queue when they cancel matchmaking.
        """
        queue_key = get_queue_key(player_count)
        
        # Remove the player from the list
        removed_count = await self.redis.lrem(queue_key, 0, player_id)
        return removed_count > 0

    async def try_match(self, player_count: int) -> list[str] | None:
        """
        Checks if there are enough players in the queue to start a game.
        If yes, it pops exactly 'player_count' players atomically using a Redis lock.
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
                    player = await self.redis.lpop(queue_key)
                    if player:
                        matched_players.append(player)
                return matched_players
                
        # Return None if there are not enough players
        return None
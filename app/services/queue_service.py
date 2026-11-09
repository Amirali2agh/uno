import json

from redis.asyncio import Redis

from app.utils.redis_keys import (
    get_player_lock_key,
    get_queue_key,
    get_queue_players_key,
)

# Game modes the server supports today.
SUPPORTED_MODES = (2, 4)


class QueueService:
    """FIFO matchmaking queues.

    Each mode keeps a list of player ids (join order) plus a hash with the player
    payloads. A player is always in at most one queue: joining one mode removes
    them from every other mode first, and per-player operations are serialised by
    a short distributed lock so concurrent joins/leaves cannot corrupt the lists.
    """

    def __init__(self, redis: Redis, lock_blocking_timeout: float = 2.0):
        # We inject the Redis client instance via constructor (Dependency Injection)
        self.redis = redis
        self.lock_blocking_timeout = lock_blocking_timeout

    def _payload_key(self, player_count: int) -> str:
        return get_queue_players_key(player_count)

    async def _locked(self, player_id: str):
        """Per-player lock so one player's join/leave cannot interleave."""
        return self.redis.lock(
            get_player_lock_key(player_id),
            timeout=10,
            blocking_timeout=self.lock_blocking_timeout,
        )

    async def join_queue(self, player_data: dict) -> bool:
        """
        Adds a player to the matchmaking queue for their mode.

        Any previous queue membership (including the other mode) is removed, so a
        player can never be matched into two games at once.
        """
        player_id = player_data["player_id"]
        player_count = player_data["player_count"]

        lock = await self._locked(player_id)
        try:
            acquired = await lock.acquire(blocking=True)
        except Exception:
            acquired = False
        if not acquired:  # pragma: no cover - extreme contention
            return False

        try:
            await self._remove_player_from_all_queues(player_id)

            pipe = self.redis.pipeline(transaction=True)
            pipe.rpush(get_queue_key(player_count), player_id)
            pipe.hset(self._payload_key(player_count), player_id, json.dumps(player_data))
            await pipe.execute()
            return True
        finally:
            try:
                await lock.release()
            except Exception:  # pragma: no cover - lock may have expired
                pass

    async def _remove_player_from_all_queues(self, player_id: str) -> bool:
        """Remove a player from every matchmaking queue. Returns True if any was removed."""
        removed = False
        for mode in SUPPORTED_MODES:
            removed = await self._remove_player_from_queue(player_id, mode) or removed
        return removed

    async def _remove_player_from_queue(self, player_id: str, player_count: int) -> bool:
        """Remove all entries for a player_id from one queue (atomic LREM)."""
        pipe = self.redis.pipeline(transaction=True)
        pipe.lrem(get_queue_key(player_count), 0, player_id)
        pipe.hdel(self._payload_key(player_count), player_id)
        removed_count, _ = await pipe.execute()
        return bool(removed_count)

    async def leave_queue(self, player_id: str, player_count: int) -> bool:
        """Removes a player from the matchmaking queue when they cancel matchmaking."""
        lock = await self._locked(player_id)
        try:
            acquired = await lock.acquire(blocking=True)
        except Exception:
            acquired = False
        if not acquired:  # pragma: no cover - extreme contention
            return False

        try:
            return await self._remove_player_from_all_queues(player_id)
        finally:
            try:
                await lock.release()
            except Exception:  # pragma: no cover
                pass

    async def queue_length(self, player_count: int) -> int:
        return await self.redis.llen(get_queue_key(player_count))

    async def try_match(self, player_count: int) -> list[dict] | None:
        """
        Checks if there are enough players in the queue to start a game.
        If yes, it pops exactly 'player_count' players atomically using a Redis lock.
        Returns list of player data dicts, or None if not enough players.
        """
        queue_key = get_queue_key(player_count)
        lock_key = f"uno:lock:queue:{player_count}"

        # Use Redis Distributed Lock to prevent concurrent matchmaking race conditions
        async with self.redis.lock(lock_key, timeout=5, blocking_timeout=5):
            current_len = await self.redis.llen(queue_key)
            if current_len < player_count:
                return None

            pipe = self.redis.pipeline(transaction=True)
            # Pop ids in FIFO order; a single transaction keeps the list and the
            # payload hash in sync.
            for _ in range(player_count):
                pipe.lpop(queue_key)
            popped = await pipe.execute()

            player_ids = [pid for pid in popped if pid]
            if len(player_ids) != player_count:  # pragma: no cover - defensive
                return None

            payload_key = self._payload_key(player_count)
            raw_payloads = await self.redis.hmget(payload_key, player_ids)
            await self.redis.hdel(payload_key, *player_ids)

            matched_players = []
            for player_id, raw in zip(player_ids, raw_payloads):
                if raw:
                    try:
                        entry = json.loads(raw)
                    except (json.JSONDecodeError, TypeError):
                        entry = None
                    if isinstance(entry, dict):
                        matched_players.append(entry)
                        continue
                # Legacy/incomplete entry: still start the game for that player.
                matched_players.append(
                    {"player_id": player_id, "player_name": "", "player_avatar": ""}
                )

            return matched_players

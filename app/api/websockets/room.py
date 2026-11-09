import json
import logging
from typing import Annotated, Literal, Optional, Union

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field, TypeAdapter, ValidationError
from redis.asyncio import Redis

from app.managers.room_manager import room_manager
from app.redis_client import get_redis
from app.services.game_service import ActionResult, GameService

logger = logging.getLogger(__name__)

# Create router for the active game room websockets
router = APIRouter()

# Reject oversized frames instead of buffering anything a client sends.
MAX_MESSAGE_CHARS = 8192


# ==========================================
# Client -> Server action payloads
# ==========================================

class DrawCardAction(BaseModel):
    action: Literal["draw_card"]


class PassTurnAction(BaseModel):
    action: Literal["pass_turn"]


class SayUnoAction(BaseModel):
    action: Literal["say_uno"]


class ChallengeUnoAction(BaseModel):
    action: Literal["challenge_uno"]


class PlayCardAction(BaseModel):
    action: Literal["play_card"]
    card_index: int = Field(ge=0, le=1000, strict=True)
    chosen_color: Optional[str] = None
    say_uno: bool = False


ActionMessage = Annotated[
    Union[
        DrawCardAction,
        PassTurnAction,
        SayUnoAction,
        ChallengeUnoAction,
        PlayCardAction,
    ],
    Field(discriminator="action"),
]

ACTION_ADAPTER: TypeAdapter[ActionMessage] = TypeAdapter(ActionMessage)


async def _send_error(websocket: WebSocket, code: str, message: str) -> None:
    """Send a structured error; the connection stays usable."""
    await websocket.send_json({"type": "error", "code": code, "message": message})


@router.websocket("/ws/room/{game_id}")
async def room_websocket(
    websocket: WebSocket,
    game_id: str,
    player_id: str,
    player_name: str = "",
    player_avatar: str = "",
    redis: Redis = Depends(get_redis),
):
    """
    WebSocket endpoint for active game play.
    URL Example: ws://localhost:8000/ws/room/abc-123?player_id=user-99&player_name=Ali&player_avatar=/avatar.jpg
    """
    game_service = GameService(redis)

    # 1. Fetch current game state to verify if this game exists
    state = await game_service.get_game_state(game_id)
    if not state:
        await websocket.close(code=4004, reason="Game not found")
        return

    # 2. Verify if the player actually belongs to this game
    if player_id not in [player.player_id for player in state.players]:
        await websocket.close(code=4003, reason="Access denied")
        return

    # 3. Accept connection and register the player in RoomManager
    await room_manager.connect(game_id, player_id, websocket, redis)

    # Notify other players that this player has connected/reconnected
    await room_manager.broadcast(game_id, {
        "type": "player_status",
        "player_id": player_id,
        "status": "connected"
    })

    # Send the current game state to the newly connected player so they can render
    # the UI. Only their own hand is included.
    await websocket.send_json({
        "type": "state_update",
        "state": state.for_player(player_id).model_dump()
    })

    try:
        # 4. Main receive loop: no client message may break this loop.
        while True:
            raw_data = await websocket.receive_text()

            if len(raw_data) > MAX_MESSAGE_CHARS:
                await _send_error(websocket, "message_too_large", "That message is too large.")
                continue

            try:
                message = json.loads(raw_data)
            except json.JSONDecodeError:
                await _send_error(websocket, "invalid_json", "Messages must be a JSON object.")
                continue

            if not isinstance(message, dict):
                await _send_error(websocket, "invalid_message", "Messages must be a JSON object.")
                continue

            try:
                action = ACTION_ADAPTER.validate_python(message)
            except ValidationError as exc:
                first = exc.errors()[0]
                detail = first.get("msg", "invalid payload")
                field = ".".join(str(part) for part in first.get("loc", ()))
                await _send_error(
                    websocket,
                    "invalid_action",
                    f"Invalid action payload ({field or 'action'}): {detail}",
                )
                continue

            try:
                result, notice = await _dispatch(game_service, game_id, player_id, action)
            except Exception:  # pragma: no cover - defensive: never drop the socket
                logger.exception("Unhandled error while processing a game action")
                await _send_error(websocket, "internal_error", "The server could not process that action.")
                continue

            if not result.ok:
                await _send_error(websocket, result.code, result.message)
                continue

            # Broadcast the new state to everyone, each with their own projection.
            new_state = await game_service.get_game_state(game_id)
            if new_state is None:
                await _send_error(websocket, "game_not_found", "That game does not exist any more.")
                continue

            extra = {"notice": notice} if notice else None
            await room_manager.broadcast_state(game_id, new_state, extra=extra)

    except WebSocketDisconnect:
        # Player closed connection or disconnected
        pass
    finally:
        # 5. Handle disconnection and start the reconnect grace period
        await room_manager.disconnect(game_id, player_id, redis)
        await room_manager.broadcast(game_id, {
            "type": "player_status",
            "player_id": player_id,
            "status": "disconnected"
        })


async def _dispatch(
    game_service: GameService,
    game_id: str,
    player_id: str,
    action: ActionMessage,
) -> tuple[ActionResult, Optional[dict]]:
    """Run one validated action; ``notice`` carries extra information for the client."""
    if isinstance(action, DrawCardAction):
        return await game_service.draw_card(game_id, player_id), None

    if isinstance(action, PassTurnAction):
        return await game_service.pass_turn(game_id, player_id), None

    if isinstance(action, SayUnoAction):
        return await game_service.say_uno(game_id, player_id), None

    if isinstance(action, ChallengeUnoAction):
        result = await game_service.challenge_uno(game_id, player_id)
        notice = (
            {"type": "uno_penalty", "player_id": result.player_id}
            if result.ok and result.player_id
            else None
        )
        return result, notice

    if isinstance(action, PlayCardAction):
        return (
            await game_service.play_card(
                game_id,
                player_id,
                action.card_index,
                action.chosen_color,
                action.say_uno,
            ),
            None,
        )

    return ActionResult(ok=False, code="invalid_action", message="Unsupported action."), None

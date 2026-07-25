import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from redis.asyncio import Redis

from app.redis_client import get_redis
from app.managers.room_manager import room_manager
from app.services.game_service import GameService
from app.services.prize_service import report_winner, update_room_status

# Create router for the active game room websockets
router = APIRouter()

@router.websocket("/ws/room/{game_id}")
async def room_websocket(websocket: WebSocket, game_id: str, player_id: str, redis: Redis = Depends(get_redis)):
    """
    WebSocket endpoint for active game play.
    URL Example: ws://localhost:8000/ws/room/abc-123?player_id=user-99
    """
    game_service = GameService(redis)
    
    # 1. Fetch current game state to verify if this game exists
    state = await game_service.get_game_state(game_id)
    if not state:
        await websocket.close(code=4004, reason="Game not found")
        return
        
    # 2. Verify if the player actually belongs to this game
    player_ids = [player.player_id for player in state.players]
    if player_id not in player_ids:
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
    
    # Send the current game state to the newly connected player so they can render the UI
    await websocket.send_json({
        "type": "state_update",
        "state": state.model_dump()
    })

    try:
        # 4. Main receive loop for player actions
        while True:
            # Wait for message from client
            raw_data = await websocket.receive_text()
            
            try:
                message = json.loads(raw_data)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "message": "Invalid JSON format"})
                continue

            action = message.get("action")

            if action == "draw_card":
                # Handle card drawing
                success = await game_service.draw_card(game_id, player_id)
                if success:
                    # Fetch new state and broadcast to everyone
                    new_state = await game_service.get_game_state(game_id)
                    await room_manager.broadcast(game_id, {
                        "type": "state_update",
                        "state": new_state.model_dump()
                    })
                else:
                    await websocket.send_json({"type": "error", "message": "Cannot draw card (not your turn)"})

            elif action == "play_card":
                # Handle card playing
                card_index = message.get("card_index")
                chosen_color = message.get("chosen_color") # Required only for Wild cards
                
                if card_index is None:
                    await websocket.send_json({"type": "error", "message": "Missing card_index"})
                    continue
                    
                success = await game_service.play_card(game_id, player_id, card_index, chosen_color)
                if success:
                    # Fetch updated state and broadcast to everyone
                    new_state = await game_service.get_game_state(game_id)
                    await room_manager.broadcast(game_id, {
                        "type": "state_update",
                        "state": new_state.model_dump()
                    })
                    # Porteghal integration: report winner + mark room finished
                    if new_state.status == "finished" and new_state.winner:
                        await report_winner(
                            room_id=game_id,
                            player_id=new_state.winner,
                            win_type="normal",
                        )
                        await update_room_status(room_id=game_id, status="finished")
                else:
                    await websocket.send_json({"type": "error", "message": "Invalid move or not your turn"})

            else:
                await websocket.send_json({"type": "error", "message": f"Unknown action: {action}"})

    except WebSocketDisconnect:
        # Player closed connection or disconnected
        pass
    finally:
        # 5. Handle disconnection and start the 60s timeout
        await room_manager.disconnect(game_id, player_id, redis)
        await room_manager.broadcast(game_id, {
            "type": "player_status",
            "player_id": player_id,
            "status": "disconnected"
        })
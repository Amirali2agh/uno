from fastapi import WebSocket

class QueueManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, player_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[player_id] = websocket

    def disconnect(self, player_id: str):
        if player_id in self.active_connections:
            del self.active_connections[player_id]

    async def send_match_found(self, player_id: str, game_id: str):
        if player_id in self.active_connections:
            websocket = self.active_connections[player_id]
            await websocket.send_json({
                "type": "match_found",
                "game_id": game_id
            })

# این همان خطی است که جا افتاده بود و پایتون دنبال آن می‌گشت
queue_manager = QueueManager()

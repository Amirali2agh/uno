import pytest
from fastapi.testclient import TestClient
from fastapi.websockets import WebSocketDisconnect
from app.main import app

# Create a test client for the FastAPI app
client = TestClient(app)

def test_invalid_player_count():
    """
    Test that the server rejects invalid player counts (e.g., 3 players).
    """
    # Expect a WebSocketDisconnect exception when connecting with invalid data
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect("/ws/queue/3?player_id=test_user"):
            pass
            
    # 1003 is the standard WebSocket code for "Unsupported Data"
    assert exc.value.code == 1003
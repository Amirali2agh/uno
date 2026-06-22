from fastapi import FastAPI
from app.api.websockets import queue

# Initialize the FastAPI application
app = FastAPI(title="UNO Game Server")

# Register the matchmaking websocket router
app.include_router(queue.router)

@app.get("/")
def read_root():
    """Health check endpoint."""
    return {"message": "UNO Game Server is running!"}
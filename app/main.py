from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.api.websockets import queue, room
from app.redis_client import redis_client

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic: Runs when the server starts (nothing needed for now)
    yield
    # Shutdown logic: Cleanly close Redis connection pool on server stop
    await redis_client.aclose()

# Initialize FastAPI with the lifespan handler
app = FastAPI(title="UNO Game Server", lifespan=lifespan)

# Register all websocket routers
app.include_router(queue.router)
app.include_router(room.router)

@app.get("/")
def read_root():
    """Health check endpoint."""
    return {"message": "UNO Game Server is running!"}

from fastapi import FastAPI
from app.api.websockets import queue, room
from app.routers import admin

# Initialize the FastAPI application without lifespan to keep Redis alive across all tests
app = FastAPI(title="UNO Game Server")

# Register all routers
app.include_router(queue.router)
app.include_router(room.router)
app.include_router(admin.router)

@app.get("/")
def read_root():
    """Health check endpoint."""
    return {"message": "UNO Game Server is running!"}

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import get_settings
from .api import websocket, rooms
from .core.whisper_session import preload_whisper_model

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: preload Whisper model
    print("[Startup] Preloading Whisper model...")
    preload_whisper_model()
    print("[Startup] Whisper model loaded")
    yield
    # Shutdown
    print("[Shutdown] Cleaning up...")

app = FastAPI(
    title="Speech Translator API",
    description="Real-time Korean-Japanese speech translation API",
    version="1.0.0",
    lifespan=lifespan
)

# CORS configuration - allow all origins for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(websocket.router)
app.include_router(rooms.router)


@app.get("/")
async def root():
    return {
        "message": "Speech Translator API",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import get_settings
from .api import websocket, rooms

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup (Soniox 모드: Whisper preload 불필요 — 1GB EC2 OOM 방지)
    print("[Startup] Speech Translator API started (Soniox mode)")
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

import logging
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from app.core.config import settings
from app.api.websocket import router as ws_router
from app.perception import get_perception_engine
from app.cognition import get_cognition_engine

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("companion.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Warm up AI perception and cognition engines on server startup."""
    logger.info("Initializing Perception Engine (YOLOv8 + MediaPipe)...")
    get_perception_engine()
    logger.info("Initializing Cognition Engine (Faster-Whisper + LangChain + Edge-TTS)...")
    get_cognition_engine()
    logger.info("All AI pipelines loaded and ready.")
    yield
    logger.info("Server shutting down.")


# Initialize FastAPI app
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Backend API and WebSocket streaming server for Real-Time Multimodal AI Companion",
    version="0.3.0",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount WebSocket routes
app.include_router(ws_router)


@app.get("/")
async def root():
    """Root status endpoint."""
    return {
        "status": "online",
        "service": settings.PROJECT_NAME,
        "phase": "Phase 3: Live Cognition & Voice Pipeline (Whisper + LangChain + Edge-TTS)",
        "websocket_url": "/ws/companion",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": settings.PROJECT_NAME}


if __name__ == "__main__":
    logger.info(f"Starting {settings.PROJECT_NAME} on http://{settings.HOST}:{settings.PORT}")
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import json
import logging
import asyncio
from typing import Set
import numpy as np
from datetime import datetime
import os
from uuid import uuid4
import socket
from pathlib import Path
import dataclasses

main_event_loop = None

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    # Load .env file from backend directory
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        print(f"[INFO] Loaded environment variables from {env_path}")
    else:
        print("[INFO] No .env file found, using system environment variables")
except ImportError:
    # python-dotenv not installed, use system environment variables
    print("[INFO] python-dotenv not installed, using system environment variables")
except Exception as e:
    print(f"[WARNING] Error loading .env file: {e}")

from config import SystemConfig
from core.audio_capture import AudioCapture
from core.chunker import AudioChunker
from core.edge_asr import EdgeASR
from core.noise import NoiseEstimator
from core.confidence import ConfidenceEstimator
from core.router import Router
from core.cloud_asr import CloudASR
from core.caption_merger import CaptionMerger, Caption
from core.database import Database

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global state
config = SystemConfig()
edge_asr = None
chunker = None
noise_estimator = None
confidence_estimator = None
router = None
cloud_asr = None
caption_merger = None
audio_capture = None
database = None

active_connections: Set[WebSocket] = set()
is_capturing = False
internet_available = True
current_session_id = None

async def check_internet_availability():
    """Check if internet connection is available (non-blocking)"""
    global internet_available
    try:
        # Try to connect to a reliable DNS server
        socket.create_connection(("8.8.8.8", 53), timeout=2)
        internet_available = True
    except OSError:
        internet_available = False
    return internet_available

async def internet_checker_loop():
    """Periodically check internet availability"""
    while True:
        await check_internet_availability()
        await asyncio.sleep(10)  # Check every 10 seconds

        
@asynccontextmanager
async def lifespan(app: FastAPI):
    global edge_asr, chunker, noise_estimator, confidence_estimator
    global router, cloud_asr, caption_merger, database, main_event_loop

    logger.info("Initializing LiveSpeak system...")

    # ✅ CAPTURE MAIN EVENT LOOP HERE
    main_event_loop = asyncio.get_running_loop()
    logger.info("Main event loop captured")

    edge_asr = EdgeASR(config)
    chunker = AudioChunker(config.audio.sample_rate, config.audio.chunk_duration_ms)
    noise_estimator = NoiseEstimator(config)
    confidence_estimator = ConfidenceEstimator(config)
    router = Router(config)

    openai_api_key = os.getenv("OPENAI_API_KEY", None)
    cloud_asr = CloudASR(config, api_key=openai_api_key)

    caption_merger = CaptionMerger(config)
    database = Database(db_path="livespeak.db")

    await check_internet_availability()
    internet_checker_task = asyncio.create_task(internet_checker_loop())

    yield

    internet_checker_task.cancel()
    if audio_capture:
        audio_capture.stop()


app = FastAPI(
    title="LiveSpeak API",
    description="Hybrid Edge+Cloud Real-time Live Captioning System",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

async def broadcast_caption(caption):
    """Broadcast caption to all connected WebSocket clients"""
    message = {
        "type": "caption",
        "data": {
            "text": caption.text,
            "source": caption.source,
            "confidence": round(caption.confidence, 3),
            "noise_score": round(caption.noise_score, 3),
            "timestamp": caption.timestamp.isoformat()
        }
    }
    
    if database and current_session_id:
        await database.save_caption_async(current_session_id, caption)
    
    # Broadcast to all connected clients
    disconnected = set()
    for connection in list(active_connections):
        try:
            await connection.send_json(message)
        except Exception as e:
            logger.error(f"Broadcast error: {e}")
            disconnected.add(connection)
    
    # Remove disconnected clients
    for connection in disconnected:
        active_connections.discard(connection)

async def process_audio_chunk(audio_chunk: np.ndarray):
    """Process a single audio chunk through the entire pipeline"""
    try:
        # Step 1: Edge ASR transcription
        edge_text, edge_raw_confidence, token_logprobs = edge_asr.transcribe(audio_chunk)
        
        # Step 2: Noise estimation (DSP-based, no ML)
        noise_score = noise_estimator.estimate_noise(audio_chunk)
        
        # Step 3: Confidence estimation (uses token log-probabilities from Faster-Whisper)
        confidence = confidence_estimator.estimate_confidence(
            edge_text, token_logprobs, edge_raw_confidence, noise_score
        )
        
        # Step 4: Intelligent routing decision
        routing_decision = router.decide_routing(
            confidence, noise_score, internet_available
        )
        
        cloud_text = None
        cloud_confidence = None
        
        # Step 5: Cloud ASR if needed (non-blocking)
        if routing_decision["use_cloud"]:
            try:
                # Pass numpy array directly (cloud_asr handles conversion)
                cloud_text, cloud_confidence = await cloud_asr.transcribe(audio_chunk)
                
                if cloud_text:
                    router.record_cloud_result(True)
                    if cloud_confidence > edge_raw_confidence:
                        await database.save_jargon_pair_async(edge_text, cloud_text)
                else:
                    router.record_cloud_result(False)
            
            except Exception as e:
                logger.warning(f"Cloud ASR failed: {e}")
                router.record_cloud_result(False)
        
        # Step 6: Merge edge and cloud captions intelligently
        caption = caption_merger.merge_captions(
            edge_text=edge_text,
            edge_confidence=edge_raw_confidence,
            cloud_text=cloud_text,
            cloud_confidence=cloud_confidence,
            noise_score=noise_score,
            timestamp=datetime.now()
        )
        
        # Step 7: Broadcast and persist caption
        if caption.text.strip():
            await broadcast_caption(caption)
            logger.info(
                f"[{caption.source.upper()}] {caption.text[:50]}... "
                f"(conf: {caption.confidence:.2f}, noise: {noise_score:.2f}, "
                f"reason: {routing_decision['reason']})"
            )
    
    except Exception as e:
        logger.error(f"Error processing audio chunk: {e}")


def audio_callback(chunk: np.ndarray):
    global is_capturing, main_event_loop

    if not is_capturing or main_event_loop is None:
        return

    chunks = chunker.add_audio(chunk)
    for audio_chunk in chunks:
        main_event_loop.call_soon_threadsafe(
            asyncio.create_task,
            process_audio_chunk(audio_chunk)
        )



@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "capturing": is_capturing,
        "internet_available": internet_available,
        "connected_clients": len(active_connections),
        "active_session": current_session_id is not None
    }

@app.get("/stats")
async def get_stats():
    """Get system statistics and metrics"""
    stats = {
        "router_stats": router.get_stats() if router else {},
        "config": {
            "sample_rate": config.audio.sample_rate,
            "chunk_duration_ms": config.audio.chunk_duration_ms,
            "edge_model": config.edge_asr.model_size,
            "confidence_threshold": config.confidence.min_confidence_threshold,
            "noise_threshold": config.noise.noise_threshold,
            "cloud_asr_enabled": config.routing.enable_cloud_asr
        },
        "system": {
            "is_capturing": is_capturing,
            "internet_available": internet_available,
            "connected_clients": len(active_connections),
            "current_session": current_session_id
        }
    }
    
    if database:
        jargon_pairs = database.get_jargon_corrections(limit=10)
        stats["jargon_learned"] = len(jargon_pairs)
    
    return stats

@app.post("/session/start")
async def start_session():
    """Start a new captioning session"""
    global current_session_id
    
    if current_session_id:
        return {"status": "session_already_active", "session_id": current_session_id}
    
    current_session_id = str(uuid4())
    logger.info(f"Started session: {current_session_id}")
    
    return {"status": "session_started", "session_id": current_session_id}

@app.post("/session/end")
async def end_session():
    """End the current captioning session"""
    global current_session_id
    
    if not current_session_id:
        raise HTTPException(status_code=400, detail="No active session")
    
    session_id = current_session_id
    current_session_id = None
    
    logger.info(f"Ended session: {session_id}")
    
    return {"status": "session_ended", "session_id": session_id}

@app.post("/capture/start")
async def start_capture():
    """Start audio capture and processing"""
    global is_capturing, audio_capture
    
    if is_capturing:
        raise HTTPException(status_code=400, detail="Capture already running")
    
    try:
        is_capturing = True
        
        # Start audio capture
        audio_capture = AudioCapture(config, audio_callback)
        audio_capture.start()
        
        logger.info("Audio capture started")
        return {"status": "capture_started"}
    
    except Exception as e:
        is_capturing = False
        logger.error(f"Failed to start capture: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/capture/stop")
async def stop_capture():
    """Stop audio capture and processing"""
    global is_capturing, audio_capture
    
    if not is_capturing:
        raise HTTPException(status_code=400, detail="Capture not running")
    
    is_capturing = False
    
    if audio_capture:
        # Flush remaining audio in chunker
        remaining = chunker.flush()
        if remaining is not None:
            await process_audio_chunk(remaining)
        
        audio_capture.stop()
        audio_capture = None
    
    logger.info("Audio capture stopped")
    return {"status": "capture_stopped"}

@app.get("/captions/history")
async def get_caption_history(limit: int = 50):
    """Get caption history for current session"""
    if not current_session_id:
        raise HTTPException(status_code=400, detail="No active session")
    
    if not database:
        return []
    
    return database.get_captions(current_session_id, limit=limit)

@app.get("/jargon/corrections")
async def get_jargon_corrections(limit: int = 50):
    """Get learned jargon corrections (enterprise feature)"""
    if not database:
        return []
    
    return database.get_jargon_corrections(limit=limit)


@app.websocket("/ws/captions")
async def websocket_captions(websocket: WebSocket):
    """WebSocket endpoint for real-time caption streaming"""
    await websocket.accept()
    active_connections.add(websocket)
    
    logger.info(f"Client connected. Total connections: {len(active_connections)}")
    
    # Send initial system info
    await websocket.send_json({
        "type": "system_info",
        "data": {
            "sample_rate": config.audio.sample_rate,
            "chunk_duration_ms": config.audio.chunk_duration_ms,
            "edge_model": config.edge_asr.model_size,
            "cloud_asr_enabled": config.routing.enable_cloud_asr
        }
    })
    
    try:
        while True:
            # Keep connection alive and handle client commands
            data = await websocket.receive_text()
            
            if data == "ping":
                await websocket.send_json({"type": "pong"})
            
            elif data == "get_stats":
                stats = router.get_stats() if router else {}
                await websocket.send_json({
                    "type": "stats",
                    "data": stats
                })
            
            elif data == "get_history":
                if current_session_id and database:
                    history = database.get_captions(current_session_id, limit=50)
                    await websocket.send_json({
                        "type": "history",
                        "data": history
                    })
    
    except WebSocketDisconnect:
        active_connections.remove(websocket)
        logger.info(f"Client disconnected. Total connections: {len(active_connections)}")
    
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        active_connections.discard(websocket)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
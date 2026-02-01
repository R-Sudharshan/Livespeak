import asyncio
import threading
import time
import numpy as np
import os
import math
import tempfile

from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from faster_whisper import WhisperModel
import scipy.io.wavfile as wavfile

from openai import OpenAI
from dotenv import load_dotenv

# ----------------------------------------------------
# ENV
# ----------------------------------------------------
# Look in current dir, then one level up
if not load_dotenv():
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

# ----------------------------------------------------
# CONFIG
# ----------------------------------------------------
SAMPLE_RATE = 16000
WINDOW_SECONDS = 2.5
STRIDE_SECONDS = 0.5
MODEL_SIZE = "small.en"
BEAM_SIZE = 5
CLOUD_CONFIDENCE_THRESHOLD = 0.7

# ----------------------------------------------------
# GLOBAL STATE
# ----------------------------------------------------
model = None
openai_client = None
is_running = False
debug_wav_saved = False

# Statistics
stats = {
    "total_chunks": 0,
    "edge_only": 0,
    "routed_to_cloud": 0,
    "cloud_succeeded": 0,
    "edge_percentage": 100.0,
    "cloud_percentage": 0.0,
    "cloud_success_rate": 0.0,
}

# ----------------------------------------------------
# STATS HELPERS
# ----------------------------------------------------
def update_stats(source, succeeded=True):
    stats["total_chunks"] += 1

    if source == "LOCAL":
        stats["edge_only"] += 1
    elif source == "CLOUD":
        stats["routed_to_cloud"] += 1
        if succeeded:
            stats["cloud_succeeded"] += 1

    total = stats["total_chunks"]
    if total > 0:
        stats["edge_percentage"] = (stats["edge_only"] / total) * 100
        stats["cloud_percentage"] = (stats["routed_to_cloud"] / total) * 100

    if stats["routed_to_cloud"] > 0:
        stats["cloud_success_rate"] = (
            stats["cloud_succeeded"] / stats["routed_to_cloud"]
        ) * 100


# ----------------------------------------------------
# MODEL LOADING
# ----------------------------------------------------
def load_model():
    global model, openai_client

    print(f"[BACKEND] Loading Faster-Whisper ({MODEL_SIZE})...")
    try:
        model = WhisperModel(
            MODEL_SIZE,
            device="cpu",
            compute_type="int8"
        )
        print("[BACKEND] Local model loaded.")
    except Exception as e:
        print(f"[BACKEND] Error loading local model: {e}")

    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        try:
            openai_client = OpenAI(api_key=api_key)
            print("[BACKEND] OpenAI client initialized.")
        except Exception as e:
            print(f"[BACKEND] Error initializing OpenAI client: {e}")
    else:
        print("[BACKEND] WARNING: OPENAI_API_KEY not found. Cloud fallback disabled.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    threading.Thread(target=load_model, daemon=True).start()
    yield


# ----------------------------------------------------
# FASTAPI APP
# ----------------------------------------------------
app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------------------------------------------
# CONTROL ENDPOINTS
# ----------------------------------------------------
@app.post("/capture/start")
async def start_capture():
    global is_running, debug_wav_saved
    is_running = True
    debug_wav_saved = False
    print("[BACKEND] Capture started")
    return {"status": "started"}


@app.post("/capture/stop")
async def stop_capture():
    global is_running
    is_running = False
    print("[BACKEND] Capture stopped")
    return {"status": "stopped"}


# ----------------------------------------------------
# TRANSCRIPTION HELPERS
# ----------------------------------------------------
def transcribe_sync(audio_data):
    if model is None:
        return "", 0.0

    segments, _ = model.transcribe(
        audio_data,
        beam_size=BEAM_SIZE,
        language="en",
        task="transcribe",
        temperature=0.0,
        vad_filter=False,
        condition_on_previous_text=False,
        word_timestamps=True,
    )

    segments = list(segments)
    if not segments:
        return "", 0.0

    text = " ".join(s.text for s in segments).strip()
    avg_logprob = sum(s.avg_logprob for s in segments) / len(segments)
    confidence = math.exp(avg_logprob)

    return text, confidence


def transcribe_cloud(audio_data):
    if openai_client is None:
        return "", 0.0

    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as temp_wav:
            audio_int16 = (audio_data * 32768.0).astype(np.int16)
            wavfile.write(temp_wav.name, SAMPLE_RATE, audio_int16)

            with open(temp_wav.name, "rb") as audio_file:
                transcript = openai_client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    response_format="json",
                )

        return transcript.get("text", "").strip(), 1.0

    except Exception as e:
        print(f"[CLOUD] Transcription error: {e}")
        return "", 0.0


# ----------------------------------------------------
# WEBSOCKET
# ----------------------------------------------------
@app.websocket("/ws/captions")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("[BACKEND] WebSocket connected")

    buffer_capacity = int(SAMPLE_RATE * 10)
    audio_buffer = np.zeros(buffer_capacity, dtype=np.float32)

    state = {
        "buffer_ptr": 0,
        "total_samples": 0,
    }

    stop_event = asyncio.Event()
    buffer_lock = asyncio.Lock()

    async def run_transcriber():
        last_transcribe_time = time.time()
        last_committed_text = ""
        last_interim_text = ""

        print("[TRANSCRIPTION] Task started")

        while not stop_event.is_set():
            now = time.time()
            if now - last_transcribe_time < STRIDE_SECONDS:
                await asyncio.sleep(0.05)
                continue

            if model is None:
                await asyncio.sleep(0.5)
                continue

            last_transcribe_time = now

            async with buffer_lock:
                ptr = state["buffer_ptr"]
                window_samples = int(WINDOW_SECONDS * SAMPLE_RATE)

                if ptr < SAMPLE_RATE:
                    continue

                if ptr >= window_samples:
                    segment = audio_buffer[ptr - window_samples : ptr].copy()
                else:
                    segment = audio_buffer[:ptr].copy()

            max_amp = np.max(np.abs(segment))
            if max_amp < 0.01:
                if last_interim_text and last_interim_text != last_committed_text:
                    await websocket.send_json({
                        "type": "segment_final",
                        "text": last_interim_text,
                        "timestamp": now,
                    })
                    last_committed_text = last_interim_text
                    last_interim_text = ""
                continue

            loop = asyncio.get_running_loop()
            text, confidence = await loop.run_in_executor(
                None, transcribe_sync, segment
            )

            source = "LOCAL"

            if text and confidence < CLOUD_CONFIDENCE_THRESHOLD and openai_client:
                cloud_text, cloud_conf = await loop.run_in_executor(
                    None, transcribe_cloud, segment
                )
                if cloud_text:
                    text = cloud_text
                    confidence = cloud_conf
                    source = "CLOUD"
                    update_stats("CLOUD", True)
                else:
                    update_stats("CLOUD", False)
            else:
                update_stats("LOCAL")

            if text:
                last_interim_text = text

            await websocket.send_json({
                "type": "window_update",
                "text": text,
                "confidence": confidence,
                "source": source,
                "timestamp": now,
            })

            await websocket.send_json({
                "type": "stats",
                "data": stats,
            })

        print("[TRANSCRIPTION] Task finished")

    transcriber_task = asyncio.create_task(run_transcriber())

    try:
        while True:
            message = await websocket.receive()

            if message["type"] == "websocket.disconnect":
                break

            if "bytes" in message and is_running:
                chunk = (
                    np.frombuffer(message["bytes"], dtype=np.int16)
                    .astype(np.float32)
                    / 32768.0
                )

                async with buffer_lock:
                    ptr = state["buffer_ptr"]
                    if ptr + len(chunk) > buffer_capacity:
                        keep = int(WINDOW_SECONDS * 2 * SAMPLE_RATE)
                        keep = min(keep, ptr)
                        audio_buffer[:keep] = audio_buffer[ptr - keep : ptr]
                        state["buffer_ptr"] = keep
                        ptr = keep

                    audio_buffer[ptr : ptr + len(chunk)] = chunk
                    state["buffer_ptr"] += len(chunk)
                    state["total_samples"] += len(chunk)

    except WebSocketDisconnect:
        print("[RECEIVER] WebSocket disconnected")
    finally:
        stop_event.set()
        await transcriber_task
        print("[BACKEND] WebSocket closed")


# ----------------------------------------------------
# ENTRYPOINT
# ----------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)

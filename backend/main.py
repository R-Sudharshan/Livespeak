import asyncio
import logging
import numpy as np
from datetime import datetime
from typing import Optional

from config import SystemConfig
from core.audio_capture import AudioCapture
from core.chunker import AudioChunker
from core.edge_asr import EdgeASR
from core.noise import NoiseEstimator
from core.confidence import ConfidenceEstimator
from core.router import Router
from core.cloud_asr import CloudASR
from core.caption_merger import CaptionMerger
from server import app, broadcast_caption, is_capturing, internet_available

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LiveSpeakPipeline:
    """Main pipeline orchestrating the entire transcription flow"""
    
    def __init__(self):
        self.config = SystemConfig()
        self.edge_asr = EdgeASR(self.config)
        self.chunker = AudioChunker(self.config.audio.sample_rate, self.config.audio.chunk_duration_ms)
        self.noise_estimator = NoiseEstimator(self.config)
        self.confidence_estimator = ConfidenceEstimator(self.config)
        self.router = Router(self.config)
        self.cloud_asr = CloudASR(self.config, api_key=None)
        self.caption_merger = CaptionMerger(self.config)
        
        self.audio_capture = None
        self.processing_task = None
        self.is_running = False
    
    def audio_callback(self, chunk: np.ndarray):
        """Called when audio chunk is captured"""
        chunks = self.chunker.add_audio(chunk)
        for audio_chunk in chunks:
            asyncio.create_task(self.process_chunk(audio_chunk))
    
    async def process_chunk(self, audio_chunk: np.ndarray):
        """Process a single audio chunk through the pipeline"""
        # Step 1: Edge ASR
        edge_text, edge_raw_confidence, token_logprobs = self.edge_asr.transcribe(audio_chunk)
        
        # Step 2: Noise estimation
        noise_score = self.noise_estimator.estimate_noise(audio_chunk)
        
        # Step 3: Confidence estimation (uses token log-probabilities)
        confidence = self.confidence_estimator.estimate_confidence(
            edge_text, token_logprobs, edge_raw_confidence, noise_score
        )
        
        # Step 4: Routing decision
        routing_decision = self.router.decide_routing(
            confidence, noise_score, internet_available
        )
        
        cloud_text = None
        cloud_confidence = None
        
        # Step 5: Cloud ASR (if needed and available)
        if routing_decision["use_cloud"]:
            try:
                cloud_text, cloud_confidence = await self.cloud_asr.transcribe(audio_chunk)
                if cloud_text:
                    self.router.record_cloud_result(True)
                else:
                    self.router.record_cloud_result(False)
            except Exception as e:
                logger.warning(f"Cloud ASR failed: {e}")
                self.router.record_cloud_result(False)
        
        # Step 6: Caption merging
        caption = self.caption_merger.merge_captions(
            edge_text=edge_text,
            edge_confidence=edge_raw_confidence,
            cloud_text=cloud_text,
            cloud_confidence=cloud_confidence,
            noise_score=noise_score,
            timestamp=datetime.now()
        )
        
        # Step 7: Broadcast to clients
        if caption.text.strip():
            await broadcast_caption(caption)
            logger.info(
                f"[{caption.source.upper()}] {caption.text[:50]}... "
                f"(conf: {caption.confidence:.2f}, noise: {noise_score:.2f})"
            )
    
    def start(self):
        """Start the pipeline"""
        if self.is_running:
            logger.warning("Pipeline already running")
            return
        
        logger.info("Starting LiveSpeak pipeline...")
        self.is_running = True
        
        self.audio_capture = AudioCapture(self.config, self.audio_callback)
        self.audio_capture.start()
        
        logger.info("Pipeline started")
    
    def stop(self):
        """Stop the pipeline"""
        if not self.is_running:
            return
        
        logger.info("Stopping LiveSpeak pipeline...")
        self.is_running = False
        
        if self.audio_capture:
            self.audio_capture.stop()
        
        # Flush remaining audio
        remaining = self.chunker.flush()
        if remaining is not None:
            asyncio.create_task(self.process_chunk(remaining))
        
        logger.info("Pipeline stopped")

# Global pipeline instance
pipeline = None

async def main():
    """Run FastAPI server"""
    import uvicorn
    
    global pipeline
    pipeline = LiveSpeakPipeline()
    
    config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()

if __name__ == "__main__":
    asyncio.run(main())

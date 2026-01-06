import sounddevice as sd
import numpy as np
from typing import Callable, Optional
from threading import Thread, Event
import logging

logger = logging.getLogger(__name__)

class AudioCapture:
    """Captures audio from microphone in real-time chunks"""
    
    def __init__(self, config, callback: Callable[[np.ndarray], None]):
        self.config = config
        self.callback = callback
        self.stream = None
        self.stop_event = Event()
        self.is_running = False
        
    def audio_callback(self, indata, frames, time_info, status):
        """Called by sounddevice for each audio chunk"""
        if status:
            logger.warning(f"Audio capture status: {status}")
        
        # Extract audio data and trigger callback
        audio_chunk = indata[:, 0].copy()
        self.callback(audio_chunk)
    
    def start(self):
        """Start capturing audio"""
        if self.is_running:
            logger.warning("Audio capture already running")
            return
        
        self.stop_event.clear()
        self.stream = sd.InputStream(
            channels=self.config.audio.channels,
            samplerate=self.config.audio.sample_rate,
            blocksize=self.config.audio.chunk_size,
            dtype=self.config.audio.dtype,
            callback=self.audio_callback,
            latency='low'
        )
        self.stream.start()
        self.is_running = True
        logger.info("Audio capture started")
    
    def stop(self):
        """Stop capturing audio"""
        if not self.is_running:
            return
        
        self.stop_event.set()
        if self.stream:
            self.stream.stop()
            self.stream.close()
        self.is_running = False
        logger.info("Audio capture stopped")
    
    def __enter__(self):
        self.start()
        return self
    
    def __exit__(self, *args):
        self.stop()

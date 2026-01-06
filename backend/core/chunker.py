import numpy as np
from collections import deque
import logging

logger = logging.getLogger(__name__)

class AudioChunker:
    """Buffers and yields fixed-size audio chunks"""
    
    def __init__(self, sample_rate: int, chunk_duration_ms: int):
        self.sample_rate = sample_rate
        self.chunk_duration_ms = chunk_duration_ms
        self.chunk_size = int(sample_rate * chunk_duration_ms / 1000)
        self.buffer = deque()
        self.buffered_samples = 0
    
    def add_audio(self, audio: np.ndarray) -> list:
        """Add audio samples and return complete chunks"""
        self.buffer.append(audio)
        self.buffered_samples += len(audio)
        
        chunks = []
        while self.buffered_samples >= self.chunk_size:
            chunk = self._extract_chunk()
            if chunk is not None:
                chunks.append(chunk)
                self.buffered_samples -= self.chunk_size
        
        return chunks
    
    def _extract_chunk(self) -> np.ndarray:
        """Extract a chunk from the buffer"""
        chunk = np.array([], dtype=np.float32)
        
        while len(chunk) < self.chunk_size and self.buffer:
            audio = self.buffer.popleft()
            chunk = np.concatenate([chunk, audio])
        
        if len(chunk) == self.chunk_size:
            return chunk
        
        # Put back incomplete data
        if len(chunk) > 0:
            self.buffer.appendleft(chunk)
        return None
    
    def flush(self) -> np.ndarray:
        """Get remaining audio (may be smaller than chunk_size)"""
        if self.buffered_samples == 0:
            return None
        
        chunk = np.array([], dtype=np.float32)
        while self.buffer:
            chunk = np.concatenate([chunk, self.buffer.popleft()])
        
        self.buffered_samples = 0
        return chunk if len(chunk) > 0 else None

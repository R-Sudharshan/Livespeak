"""
Cloud ASR Module - OpenAI Whisper API
Called ONLY when confidence is low OR noise is high
Must be optional and non-blocking
"""
import logging
from typing import Tuple, Optional
import asyncio
import numpy as np
import io
import wave
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

class CloudASR:
    """
    Cloud ASR integration using OpenAI Whisper API.
    Only called when edge ASR confidence is low or noise is high.
    Non-blocking and gracefully handles failures.
    """
    
    def __init__(self, config, api_key: Optional[str] = None):
        self.config = config
        self.provider = config.routing.cloud_asr_provider
        self.api_key = api_key
        self.client = None
        self.timeout = config.routing.timeout_cloud_asr
        
        # Initialize OpenAI client if API key is provided
        if self.provider == "openai" and api_key:
            try:
                self.client = AsyncOpenAI(api_key=api_key)
                logger.info("Cloud ASR (OpenAI Whisper) initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Cloud ASR client: {e}")
                self.client = None
        else:
            logger.warning(
                f"Cloud ASR not configured: provider={self.provider}, "
                f"api_key={'provided' if api_key else 'missing'}"
            )
    
    def is_available(self) -> bool:
        """Check if cloud ASR is available and configured"""
        return self.client is not None
    
    async def transcribe(self, audio_input) -> Tuple[str, float]:
        """
        Transcribe audio using cloud ASR (non-blocking, async).
        
        Args:
            audio_input: Audio samples as numpy array (float32, 16kHz) or bytes
        
        Returns:
            Tuple of (text, confidence):
            - text: Transcribed text (empty if failed)
            - confidence: Confidence score in [0, 1] (0.0 if failed)
        """
        if not self.client:
            logger.debug("Cloud ASR not available, skipping")
            return "", 0.0
        
        try:
            # Convert input to WAV bytes for API
            if isinstance(audio_input, np.ndarray):
                audio_bytes = self._numpy_to_wav_bytes(audio_input)
            elif isinstance(audio_input, bytes):
                audio_bytes = audio_input
            else:
                logger.error(f"Unsupported audio input type: {type(audio_input)}")
                return "", 0.0
            
            # Call OpenAI Whisper API with timeout
            transcript = await asyncio.wait_for(
                self.client.audio.transcriptions.create(
                    model="whisper-1",
                    file=("audio.wav", audio_bytes),
                    language="en",
                    response_format="verbose_json"
                ),
                timeout=self.timeout
            )
            
            # Extract text and confidence
            text = transcript.text.strip() if hasattr(transcript, 'text') else ""
            
            # OpenAI Whisper API doesn't provide explicit confidence scores
            # We use a high default confidence (0.9) since cloud ASR is typically accurate
            # If the API returns a result, we assume high confidence
            confidence = 0.9
            
            # If verbose_json format provides segments with confidence, use it
            if hasattr(transcript, 'segments') and transcript.segments:
                # Average confidence from segments if available
                confidences = []
                for segment in transcript.segments:
                    if hasattr(segment, 'no_speech_prob'):
                        # no_speech_prob is inverse confidence
                        seg_confidence = 1.0 - segment.no_speech_prob
                        confidences.append(seg_confidence)
                
                if confidences:
                    confidence = float(np.mean(confidences))
            
            logger.info(f"Cloud ASR succeeded: {text[:50]}... (confidence: {confidence:.2f})")
            return text, confidence
        
        except asyncio.TimeoutError:
            logger.warning(f"Cloud ASR timeout after {self.timeout}s")
            return "", 0.0
        
        except Exception as e:
            logger.error(f"Cloud ASR error: {e}", exc_info=True)
            return "", 0.0
    
    def _numpy_to_wav_bytes(self, audio: np.ndarray) -> bytes:
        """
        Convert numpy audio array to WAV format bytes.
        
        Args:
            audio: Audio samples as numpy array (float32, 16kHz)
        
        Returns:
            WAV file bytes
        """
        # Ensure audio is float32 and normalized to [-1, 1]
        if audio.dtype != np.float32:
            audio = audio.astype(np.float32)
        
        # Normalize to [-1, 1] range
        max_val = np.abs(audio).max()
        if max_val > 1.0:
            audio = audio / max_val
        
        # Convert to int16 for WAV format
        audio_int16 = (audio * 32767.0).astype(np.int16)
        
        # Create WAV file in memory
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, 'wb') as wav_file:
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)  # 16-bit (2 bytes)
            wav_file.setframerate(16000)  # 16kHz sample rate
            wav_file.writeframes(audio_int16.tobytes())
        
        wav_buffer.seek(0)
        return wav_buffer.read()

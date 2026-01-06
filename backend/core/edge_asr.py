"""
Edge ASR Module - Faster-Whisper Base Model
Offline, CPU-compatible ASR for real-time transcription
"""
import numpy as np
from faster_whisper import WhisperModel
import logging
from typing import Tuple, List

logger = logging.getLogger(__name__)

class EdgeASR:
    """
    Edge-based ASR using Faster-Whisper base model.
    Optimized for low latency (~200ms) and offline operation.
    """
    
    def __init__(self, config):
        self.config = config
        self.model = None
        self._load_model()
    
    def _load_model(self):
        """Load Faster-Whisper base model (offline, CPU-compatible)"""
        logger.info(f"Loading Faster-Whisper {self.config.edge_asr.model_size} model...")
        try:
            self.model = WhisperModel(
                self.config.edge_asr.model_size,
                device=self.config.edge_asr.device,
                compute_type=self.config.edge_asr.compute_type,
                language=self.config.edge_asr.language
            )
            logger.info("Edge ASR model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load Edge ASR model: {e}")
            raise
    
    def transcribe(self, audio_chunk: np.ndarray) -> Tuple[str, float, List[float]]:
        """
        Transcribe audio chunk using edge ASR.
        
        Args:
            audio_chunk: Audio samples as numpy array (float32, 16kHz)
        
        Returns:
            Tuple of (text, confidence_score, token_logprobs):
            - text: Transcribed text
            - confidence_score: Confidence in range [0, 1]
            - token_logprobs: List of token log-probabilities for confidence estimation
        """
        try:
            # Transcribe with word-level timestamps for token log-probabilities
            segments, info = self.model.transcribe(
                audio_chunk,
                language=self.config.edge_asr.language,
                beam_size=5,
                best_of=5,
                temperature=0.0,
                vad_filter=True,
                vad_parameters=dict(threshold=0.5),
                word_level=True
            )
            
            text = ""
            token_logprobs = []
            segment_confidences = []
            
            # Extract text and token log-probabilities from segments
            for segment in segments:
                text += segment.text + " "
                
                # Get average log-probability for this segment
                if hasattr(segment, 'avg_logprob'):
                    segment_confidences.append(segment.avg_logprob)
                
                # Extract word-level log-probabilities if available
                if hasattr(segment, 'words'):
                    for word in segment.words:
                        if hasattr(word, 'probability'):
                            # Convert probability to log-probability if needed
                            token_logprobs.append(np.log(max(word.probability, 1e-10)))
                        elif hasattr(word, 'logprob'):
                            token_logprobs.append(word.logprob)
            
            # Compute confidence from token log-probabilities
            # Average log-probability converted to confidence [0, 1]
            if token_logprobs:
                avg_logprob = np.mean(token_logprobs)
                # Convert log-probability to confidence: exp(logprob) gives probability
                # Normalize to [0, 1] range (logprobs are typically negative)
                # Typical logprobs range from -inf to 0, so we use sigmoid-like transformation
                confidence = min(1.0, max(0.0, np.exp(avg_logprob)))
            elif segment_confidences:
                # Fallback to segment-level confidence
                avg_logprob = np.mean(segment_confidences)
                confidence = min(1.0, max(0.0, np.exp(avg_logprob)))
            else:
                # No confidence information available
                confidence = 0.5
            
            return text.strip(), confidence, token_logprobs
        
        except Exception as e:
            logger.error(f"Edge ASR transcription error: {e}", exc_info=True)
            return "", 0.0, []

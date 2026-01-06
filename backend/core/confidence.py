"""
Confidence Estimation Module
Uses token log-probabilities from Faster-Whisper (no ML training required)
"""
import numpy as np
import logging
from typing import List

logger = logging.getLogger(__name__)

class ConfidenceEstimator:
    """
    Estimates ASR confidence from Faster-Whisper token log-probabilities.
    No ML training required - uses explainable statistical methods.
    """
    
    def __init__(self, config):
        self.config = config
        self.confidence_history = []
        self.window_size = 10
    
    def estimate_confidence(self, text: str, token_logprobs: List[float],
                           edge_raw_confidence: float, noise_score: float) -> float:
        """
        Estimate overall confidence score from token log-probabilities.
        
        Args:
            text: Transcribed text
            token_logprobs: List of token log-probabilities from Faster-Whisper
            edge_raw_confidence: Raw confidence from edge ASR
            noise_score: Noise level in [0, 1]
        
        Returns:
            Confidence score in range [0, 1]
        """
        if not text or len(text.strip()) == 0:
            return 0.0
        
        # Primary confidence from token log-probabilities
        if token_logprobs:
            # Compute mean log-probability
            avg_logprob = np.mean(token_logprobs)
            
            # Convert log-probability to confidence [0, 1]
            # Log-probabilities are negative, so we normalize them
            # Typical range: -10 to 0, we map to [0, 1]
            # Using sigmoid-like transformation: 1 / (1 + exp(-k * logprob))
            # Or simpler: exp(logprob) gives probability, clamp to [0, 1]
            token_confidence = min(1.0, max(0.0, np.exp(avg_logprob)))
        else:
            # Fallback to edge raw confidence if no token logprobs
            token_confidence = edge_raw_confidence
        
        # Combine with edge raw confidence (weighted average)
        combined_confidence = 0.7 * token_confidence + 0.3 * edge_raw_confidence
        
        # Apply noise penalty (reduce confidence if noise is high)
        # Noise penalty: up to 30% reduction
        noise_penalty = noise_score * 0.3
        adjusted_confidence = combined_confidence * (1.0 - noise_penalty)
        
        # Track history for smoothing
        self.confidence_history.append(adjusted_confidence)
        if len(self.confidence_history) > self.window_size:
            self.confidence_history.pop(0)
        
        # Optional: Apply exponential moving average for stability
        if len(self.confidence_history) > 1:
            alpha = 0.3  # Smoothing factor
            smoothed_confidence = alpha * adjusted_confidence + (1 - alpha) * self.confidence_history[-2]
            adjusted_confidence = smoothed_confidence
        
        # Ensure confidence is in valid range
        final_confidence = min(1.0, max(0.0, adjusted_confidence))
        
        logger.debug(
            f"Confidence estimation: token={token_confidence:.3f}, "
            f"edge={edge_raw_confidence:.3f}, noise_penalty={noise_penalty:.3f}, "
            f"final={final_confidence:.3f}"
        )
        
        return final_confidence
    
    def get_confidence_stats(self) -> dict:
        """Get confidence statistics for monitoring"""
        if not self.confidence_history:
            return {"mean": 0.0, "min": 0.0, "max": 0.0, "std": 0.0}
        
        confidences = np.array(self.confidence_history)
        return {
            "mean": float(np.mean(confidences)),
            "min": float(np.min(confidences)),
            "max": float(np.max(confidences)),
            "std": float(np.std(confidences))
        }

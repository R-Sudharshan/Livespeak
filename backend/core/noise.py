"""
Noise Estimation Module
Uses DSP features (RMS, Zero-Crossing Rate) - NO ML required
"""
import numpy as np
import logging

logger = logging.getLogger(__name__)

class NoiseEstimator:
    """
    Estimates noise level using DSP features (RMS, Zero-Crossing Rate).
    No machine learning - pure signal processing for explainability.
    """
    
    def __init__(self, config):
        self.config = config
        self.rms_history = []
        self.zcr_history = []
        self.window_size = 10
        self.baseline_rms = None
        self.baseline_zcr = None
    
    def estimate_noise(self, audio_chunk: np.ndarray) -> float:
        """
        Estimate noise level using RMS and Zero-Crossing Rate.
        
        Args:
            audio_chunk: Audio samples as numpy array
        
        Returns:
            Noise score in range [0, 1] where:
            - 0.0 = clean audio (low noise)
            - 1.0 = very noisy audio
        """
        # Compute DSP features
        rms = self._compute_rms(audio_chunk)
        zcr = self._compute_zcr(audio_chunk)
        
        # Track history for adaptive thresholding
        self.rms_history.append(rms)
        self.zcr_history.append(zcr)
        
        if len(self.rms_history) > self.window_size:
            self.rms_history.pop(0)
            self.zcr_history.pop(0)
        
        # Establish baseline from history (adaptive)
        if len(self.rms_history) >= 5:
            self.baseline_rms = np.median(self.rms_history[-5:])
            self.baseline_zcr = np.median(self.zcr_history[-5:])
        
        # Normalize RMS relative to threshold
        # RMS threshold from config (typical clean speech: ~0.01-0.02)
        rms_normalized = min(1.0, rms / self.config.noise.rms_threshold)
        
        # Normalize ZCR relative to threshold
        # ZCR threshold from config (typical clean speech: ~0.05-0.1)
        zcr_normalized = min(1.0, zcr / self.config.noise.zcr_threshold)
        
        # Compute noise score as weighted combination
        # Higher RMS deviation and ZCR indicate noise
        noise_score = 0.6 * rms_normalized + 0.4 * zcr_normalized
        
        # If baseline is established, compute deviation from baseline
        if self.baseline_rms is not None and self.baseline_zcr is not None:
            rms_deviation = abs(rms - self.baseline_rms) / max(self.baseline_rms, 0.001)
            zcr_deviation = abs(zcr - self.baseline_zcr) / max(self.baseline_zcr, 0.001)
            
            # Combine baseline deviation with absolute noise score
            deviation_score = min(1.0, (rms_deviation + zcr_deviation) / 2.0)
            noise_score = 0.7 * noise_score + 0.3 * deviation_score
        
        # Clamp to [0, 1]
        final_noise_score = min(1.0, max(0.0, noise_score))
        
        logger.debug(
            f"Noise estimation: RMS={rms:.4f}, ZCR={zcr:.4f}, "
            f"normalized_RMS={rms_normalized:.3f}, normalized_ZCR={zcr_normalized:.3f}, "
            f"noise_score={final_noise_score:.3f}"
        )
        
        return final_noise_score
    
    def _compute_rms(self, audio: np.ndarray) -> float:
        """
        Compute RMS (Root Mean Square) energy.
        Higher RMS indicates louder audio, which may include noise.
        """
        if len(audio) == 0:
            return 0.0
        return float(np.sqrt(np.mean(audio ** 2)))
    
    def _compute_zcr(self, audio: np.ndarray) -> float:
        """
        Compute Zero-Crossing Rate (ZCR).
        Higher ZCR indicates more rapid changes (often noise).
        """
        if len(audio) < 2:
            return 0.0
        
        # Count zero crossings
        # Sign changes indicate zero crossings
        sign_changes = np.diff(np.sign(audio))
        zero_crossings = np.sum(np.abs(sign_changes)) / 2.0
        
        # Normalize by length
        zcr = zero_crossings / len(audio)
        return float(zcr)
    
    def get_noise_stats(self) -> dict:
        """Get noise statistics for monitoring"""
        if not self.rms_history or not self.zcr_history:
            return {"mean_rms": 0.0, "mean_zcr": 0.0, "mean_noise": 0.0}
        
        return {
            "mean_rms": float(np.mean(self.rms_history)),
            "mean_zcr": float(np.mean(self.zcr_history)),
            "baseline_rms": float(self.baseline_rms) if self.baseline_rms is not None else 0.0,
            "baseline_zcr": float(self.baseline_zcr) if self.baseline_zcr is not None else 0.0
        }

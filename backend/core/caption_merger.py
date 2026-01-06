import logging
from typing import Optional
from datetime import datetime
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class Caption:
    """Represents a single caption with metadata"""
    text: str
    source: str  # "edge" or "cloud"
    confidence: float
    timestamp: datetime
    noise_score: float = 0.0

class CaptionMerger:
    """Merges edge and cloud captions intelligently"""
    
    def __init__(self, config):
        self.config = config
        self.current_caption: Optional[Caption] = None
        self.history = []
        self.max_history = 100
    
    def merge_captions(self, edge_text: str, edge_confidence: float, 
                      cloud_text: Optional[str], cloud_confidence: Optional[float],
                      noise_score: float, timestamp: datetime) -> Caption:
        """
        Merge edge and cloud captions intelligently
        Cloud caption replaces edge only if significantly better
        """
        
        # If cloud provided no result, use edge
        if not cloud_text:
            caption = Caption(
                text=edge_text,
                source="edge",
                confidence=edge_confidence,
                noise_score=noise_score,
                timestamp=timestamp
            )
        else:
            # Cloud confidence is typically higher, use it if significantly better
            confidence_delta = cloud_confidence - edge_confidence
            
            if confidence_delta > 0.15 or (edge_confidence < 0.6 and cloud_confidence > 0.7):
                caption = Caption(
                    text=cloud_text,
                    source="cloud",
                    confidence=cloud_confidence,
                    noise_score=noise_score,
                    timestamp=timestamp
                )
                logger.info(f"Used cloud caption: {cloud_text[:50]}... (confidence gain: {confidence_delta:.2f})")
            else:
                caption = Caption(
                    text=edge_text,
                    source="edge",
                    confidence=edge_confidence,
                    noise_score=noise_score,
                    timestamp=timestamp
                )
        
        self.current_caption = caption
        self.history.append(caption)
        
        # Maintain history size
        if len(self.history) > self.max_history:
            self.history.pop(0)
        
        return caption
    
    def get_history(self, limit: int = 50) -> list:
        """Get caption history"""
        return self.history[-limit:]
    
    def get_current(self) -> Optional[Caption]:
        """Get current caption"""
        return self.current_caption

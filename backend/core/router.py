"""
Intelligent Routing Engine
Decides when to route audio chunks to cloud ASR based on confidence and noise
"""
import logging
from typing import Dict

logger = logging.getLogger(__name__)

class Router:
    """
    Intelligent routing engine for edge vs cloud ASR.
    Implements exact routing logic as specified:
    - Route to cloud if confidence < 0.75 OR noise > 0.6 AND internet available
    """
    
    def __init__(self, config):
        self.config = config
        self.stats = {
            "total_chunks": 0,
            "edge_only": 0,
            "routed_to_cloud": 0,
            "cloud_succeeded": 0,
            "cloud_failed": 0,
            "cloud_timeout": 0,
            "no_internet": 0
        }
    
    def decide_routing(self, confidence: float, noise_score: float, 
                      internet_available: bool) -> Dict:
        """
        Decide whether to route chunk to cloud ASR.
        
        Routing Logic (EXACT):
        if (confidence < 0.75 OR noise > 0.6) AND internet_available:
            route chunk to cloud
        else:
            keep edge output
        
        Args:
            confidence: Confidence score in [0, 1]
            noise_score: Noise score in [0, 1]
            internet_available: Whether internet connection is available
        
        Returns:
            Dictionary with routing decision and metadata:
            {
                "use_cloud": bool,
                "reason": str,
                "confidence": float,
                "noise_score": float
            }
        """
        self.stats["total_chunks"] += 1
        
        # Exact routing logic as specified
        use_cloud = False
        reason = "edge_only"
        
        # Check if cloud routing conditions are met
        low_confidence = confidence < 0.75
        high_noise = noise_score > 0.6
        
        # Route to cloud if (low confidence OR high noise) AND internet available
        if (low_confidence or high_noise) and internet_available:
            if not self.config.routing.enable_cloud_asr:
                use_cloud = False
                reason = "cloud_disabled"
            else:
                use_cloud = True
                if low_confidence and high_noise:
                    reason = "low_confidence_and_high_noise"
                elif low_confidence:
                    reason = "low_confidence"
                elif high_noise:
                    reason = "high_noise"
        else:
            # Keep edge output
            use_cloud = False
            if not internet_available:
                reason = "no_internet"
            elif not low_confidence and not high_noise:
                reason = "edge_sufficient"
            else:
                reason = "edge_only"
        
        # Update statistics
        if use_cloud:
            self.stats["routed_to_cloud"] += 1
        else:
            self.stats["edge_only"] += 1
            if not internet_available:
                self.stats["no_internet"] += 1
        
        decision = {
            "use_cloud": use_cloud,
            "reason": reason,
            "confidence": confidence,
            "noise_score": noise_score,
            "internet_available": internet_available
        }
        
        logger.debug(
            f"Routing decision: use_cloud={use_cloud}, reason={reason}, "
            f"confidence={confidence:.3f}, noise={noise_score:.3f}"
        )
        
        return decision
    
    def record_cloud_result(self, success: bool, timeout: bool = False):
        """
        Record cloud ASR outcome for statistics.
        
        Args:
            success: Whether cloud ASR succeeded
            timeout: Whether cloud ASR timed out
        """
        if timeout:
            self.stats["cloud_timeout"] += 1
            self.stats["cloud_failed"] += 1
        elif success:
            self.stats["cloud_succeeded"] += 1
        else:
            self.stats["cloud_failed"] += 1
    
    def get_stats(self) -> Dict:
        """
        Get routing statistics for monitoring and analytics.
        
        Returns:
            Dictionary with comprehensive routing statistics
        """
        total = self.stats["total_chunks"]
        if total == 0:
            return {
                **self.stats,
                "edge_percentage": 0.0,
                "cloud_percentage": 0.0,
                "cloud_success_rate": 0.0
            }
        
        routed = self.stats["routed_to_cloud"]
        edge_percentage = (self.stats["edge_only"] / total) * 100
        cloud_percentage = (routed / total) * 100
        
        cloud_success_rate = 0.0
        if routed > 0:
            cloud_success_rate = (self.stats["cloud_succeeded"] / routed) * 100
        
        return {
            **self.stats,
            "edge_percentage": round(edge_percentage, 2),
            "cloud_percentage": round(cloud_percentage, 2),
            "cloud_success_rate": round(cloud_success_rate, 2)
        }
    
    def reset_stats(self):
        """Reset routing statistics (useful for new sessions)"""
        self.stats = {
            "total_chunks": 0,
            "edge_only": 0,
            "routed_to_cloud": 0,
            "cloud_succeeded": 0,
            "cloud_failed": 0,
            "cloud_timeout": 0,
            "no_internet": 0
        }

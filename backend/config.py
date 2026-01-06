from dataclasses import dataclass, field
from typing import Optional

@dataclass
class AudioConfig:
    """Audio capture configuration"""
    sample_rate: int = 16000
    chunk_duration_ms: int = 200  # 200ms chunks for low latency
    chunk_size: int = 3200  # 16000 * 0.2
    channels: int = 1
    dtype: str = "float32"

@dataclass
class EdgeASRConfig:
    """Edge ASR configuration"""
    model_size: str = "base"  # Use base model for speed
    device: str = "cpu"
    compute_type: str = "float32"  # CPU compatible
    language: str = "en"

@dataclass
class ConfidenceConfig:
    """Confidence estimation thresholds"""
    min_confidence_threshold: float = 0.75
    low_confidence_tolerance: float = 0.5

@dataclass
class NoiseConfig:
    """Noise estimation thresholds"""
    noise_threshold: float = 0.6
    rms_threshold: float = 0.02
    zcr_threshold: float = 0.1

@dataclass
class RoutingConfig:
    """Intelligent routing configuration"""
    enable_cloud_asr: bool = True
    cloud_asr_provider: str = "openai"  # openai, google, aws, azure
    route_on_low_confidence: bool = True
    route_on_high_noise: bool = True
    timeout_cloud_asr: int = 5  # seconds

@dataclass
class SystemConfig:
    """System-wide configuration"""
    audio: AudioConfig = field(default_factory=AudioConfig)
    edge_asr: EdgeASRConfig = field(default_factory=EdgeASRConfig)
    confidence: ConfidenceConfig = field(default_factory=ConfidenceConfig)
    noise: NoiseConfig = field(default_factory=NoiseConfig)
    routing: RoutingConfig = field(default_factory=RoutingConfig)
    log_level: str = "INFO"
    enable_metrics: bool = True

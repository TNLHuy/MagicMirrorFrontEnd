"""
Voice processing subpackage: Audio Recording, RMS Streaming, Wakeword, and Local STT
"""

from .audio_recorder import AudioRecorder, RealMicrophone
from .local_stt import LocalSTT, get_local_stt
from .stt_service import HybridSTT, get_stt_engine
from .tts_service import TTSService, get_tts_engine
from .wakeword import WakeWordDetector, get_wakeword_detector

__all__ = [
    "AudioRecorder",
    "RealMicrophone",
    "LocalSTT",
    "get_local_stt",
    "HybridSTT",
    "get_stt_engine",
    "TTSService",
    "get_tts_engine",
    "WakeWordDetector",
    "get_wakeword_detector"
]


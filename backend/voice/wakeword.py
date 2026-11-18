"""
====================================================================
      WAKEWORD DETECTION ENGINE — "HEY MIRROR" (OPENWAKEWORD)
====================================================================
Bộ nhận diện từ khóa đánh thức (Wakeword / Keyword Spotting):
- Engine: openWakeWord (Audio Spectrogram Transformer / ONNX)
- Từ khóa: "Hey Mirror"
- Tệp mô hình: models/wakeword/hey_mirror.onnx (~773KB)
- Tần số mẫu: 16000Hz (khung xử lý chuẩn 80ms = 1280 samples)
- Ngưỡng kích hoạt (Threshold): Mặc định 0.35 (35%), cấu hình qua WAKEWORD_THRESHOLD
- Tối ưu hóa: Chạy 100% Offline tại biên (Edge CPU Pi 5 / x86 PC)
====================================================================
"""

import os
import sys
import time
import warnings
from typing import Optional, Tuple
import numpy as np

# Ẩn cảnh báo provider ONNX
warnings.filterwarnings("ignore")

# Đảm bảo UTF-8
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Thư viện openwakeword
try:
    from openwakeword.model import Model
    HAS_OPENWAKEWORD = True
except ImportError:
    Model = None
    HAS_OPENWAKEWORD = False

# Đường dẫn mặc định tới mô hình
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))
DEFAULT_MODEL_PATH = os.path.join(PROJECT_ROOT, "models", "wakeword", "hey_mirror.onnx")


class WakeWordDetector:
    """
    Bộ nhận diện từ khóa 'Hey Mirror' thời gian thực sử dụng openWakeWord.
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        sample_rate: int = 16000,
        chunk_size: int = 1280,
        threshold: Optional[float] = None,
        cooldown_seconds: float = 1.8
    ):
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.cooldown_seconds = cooldown_seconds

        # Ngưỡng kích hoạt (mặc định 0.35 = 35% cho openWakeWord)
        env_th = os.getenv("WAKEWORD_THRESHOLD")
        if env_th is not None:
            try:
                self.threshold = float(env_th)
            except Exception:
                self.threshold = float(threshold or 0.35)
        else:
            self.threshold = float(threshold or 0.35)

        self.model_path = model_path or self._find_model_path()
        self.oww: Optional[Model] = None
        self.model_name: Optional[str] = None
        self.is_ready = False

        # Vùng đệm xử lý tích lũy mẫu nếu chunk không đúng 1280
        self._accumulator = np.array([], dtype=np.int16)
        self._last_trigger_time = 0.0

        self._load_model()

    def _find_model_path(self) -> str:
        """Tìm đường dẫn tệp mô hình ONNX openWakeWord"""
        if os.path.exists(DEFAULT_MODEL_PATH):
            return DEFAULT_MODEL_PATH
        
        # Thử tìm file .onnx bất kỳ trong thư mục models/wakeword/
        wakeword_dir = os.path.join(PROJECT_ROOT, "models", "wakeword")
        if os.path.isdir(wakeword_dir):
            for f in os.listdir(wakeword_dir):
                if f.endswith(".onnx"):
                    return os.path.join(wakeword_dir, f)
        return DEFAULT_MODEL_PATH

    def _load_model(self):
        """Khởi tạo mô hình openWakeWord"""
        if not HAS_OPENWAKEWORD:
            print("[⚠️ WakeWord] Chưa cài đặt 'openwakeword'. Hãy chạy: pip install openwakeword")
            self.is_ready = False
            return

        if not os.path.exists(self.model_path):
            print(f"[⚠️ WakeWord] Không tìm thấy tệp mô hình tại: {self.model_path}")
            self.is_ready = False
            return

        try:
            self.oww = Model(wakeword_model_paths=[self.model_path])
            names = list(self.oww.models.keys())
            if not names:
                print(f"[❌ WakeWord] Không tải được model từ {self.model_path}")
                self.is_ready = False
                return

            self.model_name = names[0]
            self.is_ready = True
            print(f"[🟢 WakeWord] Đã tải mô hình openWakeWord: '{self.model_name}' ({os.path.basename(self.model_path)})")
        except Exception as e:
            print(f"[❌ WakeWord] Lỗi khi nạp mô hình openWakeWord: {e}")
            self.is_ready = False

    def process_chunk(self, chunk: np.ndarray) -> Tuple[bool, float]:
        """
        Xử lý 1 khối âm thanh mới từ Micro.
        
        Args:
            chunk: Mảng PCM float32 [-1.0, 1.0] hoặc int16 [-32768, 32767]
            
        Returns:
            (is_wakeword_detected: bool, score: float)
        """
        if not self.is_ready or self.oww is None:
            return False, 0.0

        # 1. Chuyển đổi sang định dạng int16 nếu là float32
        if chunk.dtype in [np.float32, np.float64]:
            chunk_int16 = np.clip(chunk * 32767.0, -32768, 32767).astype(np.int16)
        else:
            chunk_int16 = chunk.astype(np.int16)

        # 2. Tích lũy vào accumulator để đạt bội số của 1280 (80ms @ 16kHz)
        if len(self._accumulator) > 0:
            self._accumulator = np.concatenate([self._accumulator, chunk_int16])
        else:
            self._accumulator = chunk_int16

        # Nếu chưa đủ 1280 samples, đợi khung kế tiếp
        if len(self._accumulator) < 1280:
            return False, 0.0

        # Cắt ra số mẫu là bội số của 1280
        num_frames = (len(self._accumulator) // 1280) * 1280
        process_data = self._accumulator[:num_frames]
        self._accumulator = self._accumulator[num_frames:]

        now = time.time()
        in_cooldown = (now - self._last_trigger_time) < self.cooldown_seconds

        try:
            # 3. Dự đoán qua openWakeWord
            predictions = self.oww.predict(process_data)
            score = float(predictions.get(self.model_name, 0.0))

            if in_cooldown:
                return False, score

            # 4. Kiểm tra ngưỡng kích hoạt
            if score >= self.threshold:
                self._last_trigger_time = now
                self.reset()
                return True, score

            return False, score

        except Exception as e:
            return False, 0.0

    def reset(self):
        """Xóa trắng bộ nhớ đệm openWakeWord và tích lũy"""
        self._accumulator = np.array([], dtype=np.int16)
        if self.oww is not None:
            try:
                self.oww.reset()
            except Exception:
                pass


# Singleton Instance
_wakeword_instance: Optional[WakeWordDetector] = None

def get_wakeword_detector() -> WakeWordDetector:
    global _wakeword_instance
    if _wakeword_instance is None:
        _wakeword_instance = WakeWordDetector()
    return _wakeword_instance

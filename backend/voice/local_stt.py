"""
====================================================================
       LOCAL STT ENGINE — ZIPFORMER-30M-RNNT-6000h (VIETNAMESE)
====================================================================
Mô hình Nhận Dạng Giọng Nói Tiếng Việt Tại Biên (Edge Speech-to-Text):
- Kiến trúc: Zipformer RNN-Transducer (RNNT)
- Số lượng tham số: ~30 triệu (30M parameters)
- Định dạng: Quantized INT8 ONNX
- Hiệu năng CPU: ~0.3s cho đoạn âm thanh 10–12 giây trên ARM Cortex-A76 (Raspberry Pi 5)
- Thư viện runtime: sherpa-onnx (offline, không cần internet)
====================================================================
"""

import os
import sys
import time
import re
from typing import Optional, Union, Tuple
import numpy as np

# Đảm bảo UTF-8
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Thử import sherpa-onnx
try:
    import sherpa_onnx
    HAS_SHERPA_ONNX = True
except ImportError:
    sherpa_onnx = None
    HAS_SHERPA_ONNX = False

# Đường dẫn mặc định tới thư mục models/stt
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))
DEFAULT_MODEL_DIR = os.path.join(PROJECT_ROOT, "models", "stt")
FALLBACK_MODEL_DIR = r"E:\Projects\VietnameseSpeech2Text\Zipformer-30M-RNNT-6000h"

class LocalSTT:
    """
    Engine nhận dạng giọng nói tiếng Việt Zipformer-30M chạy hoàn toàn offline trên CPU.
    """

    def __init__(
        self,
        model_dir: Optional[str] = None,
        num_threads: int = 4,
        decoding_method: str = "greedy_search"
    ):
        """
        Khởi tạo mô hình Zipformer-30M RNN-T.
        
        Args:
            model_dir: Thư mục chứa các tệp model ONNX và tokens.txt
            num_threads: Số luồng CPU sử dụng (mặc định 4 nhân tương ứng 4 nhân Pi 5)
            decoding_method: "greedy_search" (nhanh nhất) hoặc "modified_beam_search"
        """
        self.model_dir = model_dir or self._find_model_dir()
        self.num_threads = num_threads
        self.decoding_method = decoding_method
        self.recognizer: Optional[sherpa_onnx.OfflineRecognizer] = None
        self.is_ready = False

        if not HAS_SHERPA_ONNX:
            print("[⚠️ LocalSTT] Chưa cài đặt thư viện 'sherpa-onnx'. Hãy chạy: pip install sherpa-onnx")
            return

        self._load_model()

    def _find_model_dir(self) -> str:
        """Tự động tìm thư mục chứa mô hình theo thứ tự ưu tiên"""
        if os.path.exists(DEFAULT_MODEL_DIR) and self._is_valid_model_dir(DEFAULT_MODEL_DIR):
            return DEFAULT_MODEL_DIR
        if os.path.exists(FALLBACK_MODEL_DIR) and self._is_valid_model_dir(FALLBACK_MODEL_DIR):
            return FALLBACK_MODEL_DIR
        return DEFAULT_MODEL_DIR

    @staticmethod
    def _is_valid_model_dir(path: str) -> bool:
        """Kiểm tra xem thư mục có đủ các tệp cần thiết hay không"""
        has_encoder = any("encoder" in f and f.endswith(".onnx") for f in os.listdir(path)) if os.path.isdir(path) else False
        has_decoder = any("decoder" in f and f.endswith(".onnx") for f in os.listdir(path)) if os.path.isdir(path) else False
        has_joiner = any("joiner" in f and f.endswith(".onnx") for f in os.listdir(path)) if os.path.isdir(path) else False
        return has_encoder and has_decoder and has_joiner

    def _load_model(self):
        """Khởi tạo OfflineRecognizer từ các file ONNX Zipformer"""
        if not os.path.exists(self.model_dir):
            print(f"[⚠️ LocalSTT] Không tìm thấy thư mục mô hình tại: {self.model_dir}")
            return

        # 1. Tìm các tệp ONNX (Ưu tiên bản lượng tử hóa .int8.onnx để tối ưu tốc độ CPU)
        files = os.listdir(self.model_dir)

        def pick_file(prefix: str) -> Optional[str]:
            # Ưu tiên .int8.onnx
            int8_candidates = [f for f in files if f.startswith(prefix) and f.endswith(".int8.onnx")]
            if int8_candidates:
                return os.path.join(self.model_dir, int8_candidates[0])
            # Fallback sang .onnx chuẩn
            onnx_candidates = [f for f in files if f.startswith(prefix) and f.endswith(".onnx")]
            if onnx_candidates:
                return os.path.join(self.model_dir, onnx_candidates[0])
            return None

        encoder_path = pick_file("encoder")
        decoder_path = pick_file("decoder")
        joiner_path = pick_file("joiner")

        # 2. Tìm tệp tokens (tokens.txt hoặc config.json)
        tokens_path = None
        for cand in ["tokens.txt", "config.json", "config"]:
            p = os.path.join(self.model_dir, cand)
            if os.path.exists(p):
                tokens_path = p
                break

        bpe_path = os.path.join(self.model_dir, "bpe.model")

        if not (encoder_path and decoder_path and joiner_path and tokens_path):
            print(f"[⚠️ LocalSTT] Thiếu tệp mô hình trong: {self.model_dir}")
            print(f"  - Encoder: {encoder_path}")
            print(f"  - Decoder: {decoder_path}")
            print(f"  - Joiner:  {joiner_path}")
            print(f"  - Tokens:  {tokens_path}")
            return

        try:
            start_t = time.time()
            print(f"[🔄 LocalSTT] Đang tải mô hình Zipformer-30M ({'INT8 Quantized' if '.int8.' in encoder_path else 'FP32'})...")

            # Khởi tạo Transducer Recognizer
            self.recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(
                encoder=encoder_path,
                decoder=decoder_path,
                joiner=joiner_path,
                tokens=tokens_path,
                num_threads=self.num_threads,
                sample_rate=16000,
                feature_dim=80,
                decoding_method=self.decoding_method,
                provider="cpu",
            )
            self.is_ready = True
            load_dur = time.time() - start_t
            print(f"[✅ LocalSTT] Đã tải thành công mô hình Zipformer-30M trong {load_dur:.2f}s!")
            print(f"  • Encoder : {os.path.basename(encoder_path)}")
            print(f"  • Decoder : {os.path.basename(decoder_path)}")
            print(f"  • Joiner  : {os.path.basename(joiner_path)}")
            print(f"  • Tokens  : {os.path.basename(tokens_path)}")
            print(f"  • Threads : {self.num_threads} CPU cores")

        except Exception as e:
            print(f"[❌ LocalSTT] Lỗi khi nạp mô hình Zipformer: {e}")
            self.is_ready = False

    @staticmethod
    def normalize_text(text: str) -> str:
        """
        Chuẩn hóa kết quả nhận diện từ mô hình:
        - Xóa các token đặc biệt như <blk>, <sos/eos>, <unk>
        - Xóa các ký tự phân tách từ đặc trưng của BPE (ví dụ: '▁', ' ')
        - Đổi thành chữ thường chuẩn tiếng Việt
        - Xóa khoảng trắng thừa
        """
        if not text:
            return ""

        # Xóa các tag đặc biệt dạng <...> hoặc dấu ngoặc nhọn mồ côi
        text = re.sub(r"<[^>]*>?", " ", text)
        text = text.replace("<", " ").replace(">", " ")
        # Xóa các ký tự phân tách từ đặc trưng của BPE
        text = text.replace("▁", " ").replace(" ", " ")
        # Xóa khoảng trắng kép
        text = re.sub(r"\s+", " ", text).strip()
        t = text.lower()
        t = re.sub(r"\b(chộp|chục)\s+(ảnh|hình)\b", r"chụp \2", t)
        if t in ["chộp", "chục", "chụp", "chộp hình", "chục hình", "chộp đi", "chộp nà", "chộp nè", "chộp ảnh"]:
            return "chụp ảnh"
        if t in ["huỷ", "thui", "thôi nha", "thôi nhé", "ngưng", "dừng", "hủy bỏ", "thoát"]:
            return "hủy"
        return t

    def transcribe_samples(
        self,
        samples: np.ndarray,
        sample_rate: int = 16000
    ) -> Tuple[str, float]:
        """
        Nhận dạng mảng âm thanh numpy (đoạn ghi âm từ micro).
        
        Args:
            samples: Mảng numpy float32 hoặc int16 1D
            sample_rate: Tần số lấy mẫu (mặc định 16000Hz)
            
        Returns:
            (văn_bản_tiếng_việt, thời_gian_xử_lý_giây)
        """
        if not self.is_ready or not self.recognizer:
            return "", 0.0

        # Chuẩn hóa về float32 nằm trong khoảng [-1.0, 1.0]
        if samples.dtype == np.int16:
            samples = samples.astype(np.float32) / 32768.0
        elif samples.dtype != np.float32:
            samples = samples.astype(np.float32)

        # Đảm bảo 1D array
        if samples.ndim > 1:
            samples = samples.squeeze()

        audio_duration = len(samples) / float(sample_rate)

        start_t = time.perf_counter()
        try:
            stream = self.recognizer.create_stream()
            stream.accept_waveform(sample_rate, samples)
            self.recognizer.decode_stream(stream)
            raw_text = stream.result.text
            clean_text = self.normalize_text(raw_text)
            latency = time.perf_counter() - start_t

            # Tính toán tỉ lệ thời gian thực RTF (Real-Time Factor)
            rtf = latency / max(audio_duration, 0.01)
            print(f"[⚡ LocalSTT] Âm thanh {audio_duration:.2f}s -> Xử lý trong {latency:.3f}s (RTF: {rtf:.3f}) | '{clean_text}'")

            return clean_text, latency
        except Exception as e:
            print(f"[❌ LocalSTT] Lỗi giải mã âm thanh: {e}")
            return "", 0.0

    def transcribe_wav(self, wav_path: str) -> Tuple[str, float]:
        """
        Nhận dạng tệp âm thanh .wav từ đĩa.
        """
        if not self.is_ready or not self.recognizer:
            return "", 0.0

        if not os.path.exists(wav_path):
            print(f"[!] Không tìm thấy file âm thanh: {wav_path}")
            return "", 0.0

        try:
            import wave
            with wave.open(wav_path, "rb") as wf:
                sample_rate = wf.getframerate()
                num_frames = wf.getnframes()
                raw_data = wf.readframes(num_frames)
                samples = np.frombuffer(raw_data, dtype=np.int16)

            return self.transcribe_samples(samples, sample_rate)
        except Exception as e:
            print(f"[❌ LocalSTT] Lỗi khi đọc file wav: {e}")
            return "", 0.0

# Singleton instance
_local_stt_instance: Optional[LocalSTT] = None

def get_local_stt() -> LocalSTT:
    """Trả về phiên bản duy nhất của LocalSTT (Singleton)"""
    global _local_stt_instance
    if _local_stt_instance is None:
        _local_stt_instance = LocalSTT()
    return _local_stt_instance

if __name__ == "__main__":
    print("=== KIỂM THỬ LOCAL STT ZIPFORMER-30M ===")
    stt = get_local_stt()
    if stt.is_ready:
        print("[+] Engine đã sẵn sàng nhận dạng!")
        # Thử nghiệm với âm thanh mẫu giả lập 3 giây
        fake_samples = np.zeros(16000 * 3, dtype=np.float32)
        text, dur = stt.transcribe_samples(fake_samples, 16000)
        print(f"[+] Kết quả kiểm thử: '{text}' (thời gian: {dur:.3f}s)")
    else:
        print("[-] Engine chưa thể khởi tạo. Vui lòng kiểm tra lại thư viện và model.")


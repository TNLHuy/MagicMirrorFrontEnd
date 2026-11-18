"""
====================================================================
        HYBRID SPEECH-TO-TEXT (STT) SERVICE
====================================================================
Hệ thống chuyển đổi giọng nói thành văn bản Hybrid (Cloud-First + Edge Fallback):
1. Groq Cloud STT (Whisper Large v3):
   - Tốc độ siêu nhanh: ~0.25s - 0.35s
   - Độ chính xác tiếng Việt 98%
   - Tự động kích hoạt khi có GROQ_API_KEY trong .env
2. Google Cloud STT (Google Web Speech API):
   - Miễn phí 100%, không cần cấu hình API key
   - Tốc độ phản hồi: ~0.6s - 0.9s
   - Nhận diện câu lệnh tiếng Việt chuẩn xác
3. Gemini Cloud STT (Flash Lite Audio):
   - Tận dụng GEMINI_API_KEY có sẵn
   - Khả năng hiểu ngữ cảnh phức tạp
4. Local STT Engine (Zipformer-30M-RNNT):
   - Chạy offline hoàn toàn trên CPU Raspberry Pi 5 (~0.1s)
   - Giữ làm lớp dự phòng (Fallback) khi mất mạng hoặc người dùng chọn STT_PROVIDER=local
====================================================================
"""

import io
import json
import os
import re
import subprocess
import sys
import time
import wave
from typing import Optional, Tuple, Union
import numpy as np

# Đảm bảo UTF-8
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Đảm bảo sys.path chứa PROJECT_ROOT
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Tải cấu hình biến môi trường từ .env
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(PROJECT_ROOT, ".env"))
except ImportError:
    pass

# Import LocalSTT engine làm fallback offline
from backend.voice.local_stt import LocalSTT, get_local_stt

# Import SpeechRecognition (Google Web Speech API)
try:
    import speech_recognition as sr
    HAS_SPEECH_RECOGNITION = True
except ImportError:
    sr = None
    HAS_SPEECH_RECOGNITION = False

# Import Google GenAI nếu có
try:
    from google import genai
    from google.genai import types
    HAS_GENAI = True
except ImportError:
    genai = None
    types = None
    HAS_GENAI = False

# Import requests cho Groq API
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    requests = None
    HAS_REQUESTS = False


class HybridSTT:
    """
    Engine nhận dạng giọng nói kết hợp Cloud STT (Groq / Google / Gemini) và Local Edge STT (Zipformer-30M).
    """

    def __init__(self, provider: Optional[str] = None):
        """
        Args:
            provider: 'auto' | 'groq' | 'google' | 'gemini' | 'local'
                      Mặc định đọc từ biến môi trường STT_PROVIDER (hoặc 'auto')
        """
        self.provider = (provider or os.getenv("STT_PROVIDER", "auto")).lower()
        self.groq_api_key = os.getenv("GROQ_API_KEY", "").strip()
        self.gemini_api_key = os.getenv("GEMINI_API_KEY", "").strip()

        # Bộ nhận dạng Google SpeechRecognition
        self.sr_recognizer = sr.Recognizer() if HAS_SPEECH_RECOGNITION else None

        # Khởi tạo Gemini Client nếu có API key
        self.gemini_client = None
        if HAS_GENAI and self.gemini_api_key:
            try:
                self.gemini_client = genai.Client(api_key=self.gemini_api_key)
            except Exception as e:
                print(f"[⚠️ HybridSTT] Không thể khởi tạo Gemini Client: {e}")

        # Khởi tạo LocalSTT (Zipformer-30M) dự phòng
        self.local_stt: LocalSTT = get_local_stt()

        self.is_ready = True
        self._print_status()

    def _print_status(self):
        active_chain = []
        if self.groq_api_key:
            active_chain.append("Groq Whisper Large v3 (~0.25s)")
        if self.sr_recognizer:
            active_chain.append("Google Cloud Speech (~0.7s Free)")
        if self.provider == "gemini" and self.gemini_client:
            active_chain.append("Gemini Flash Lite (~1.8s)")
        if self.local_stt and self.local_stt.is_ready:
            active_chain.append("Zipformer-30M INT8 (~0.1s Offline)")

        print(f"[🌐 HybridSTT] Chế độ STT: '{self.provider.upper()}' | Chuỗi ưu tiên: {' ➔ '.join(active_chain)}")

    @staticmethod
    def samples_to_wav_bytes(samples: np.ndarray, sample_rate: int = 16000) -> bytes:
        """Chuyển mảng numpy âm thanh float32 thành bytes định dạng WAV 16-bit PCM"""
        clipped = np.clip(samples, -1.0, 1.0)
        int16_data = (clipped * 32767.0).astype(np.int16)
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(int16_data.tobytes())
        return buf.getvalue()

    @staticmethod
    def apply_peak_normalization(samples: np.ndarray, target_peak: float = 0.85, max_scale: float = 5.0) -> np.ndarray:
        """
        Khuếch đại chuẩn hóa biên độ âm lượng (Peak Normalization):
        Tự động bù đắp âm lượng khi người nói đứng xa gương hoặc mic thu âm yếu.
        """
        if len(samples) == 0:
            return samples
        peak = float(np.max(np.abs(samples)))
        if peak > 0.005:
            scale = min(target_peak / peak, max_scale)
            if scale > 1.05:
                samples = np.clip(samples * scale, -1.0, 1.0)
        return samples

    @staticmethod
    def clean_transcription(text: str) -> str:
        """Làm sạch văn bản nhận diện từ các mô hình ASR"""
        if not text:
            return ""
        text = text.strip().strip('"\'`')
        # Xóa các tag HTML / Markdown
        text = re.sub(r"<[^>]*>", "", text)
        # Xóa các chú thích âm nhạc/tiếng ồn dạng [âm nhạc], (tiếng vỗ tay)
        text = re.sub(r"\[.*?\]", "", text)
        text = re.sub(r"\(.*?\)", "", text)

        # Lọc các câu ảo giác (Hallucinations) đặc trưng của Whisper khi nhận đoạn âm thanh im lặng/tạp âm
        hallucination_keywords = [
            "subscribe",
            "đăng ký kênh",
            "ghiền mì gõ",
            "kênh youtube",
            "bấm chuông",
            "like và share",
            "like and subscribe",
            "cảm ơn đã theo dõi",
            "cảm ơn các bạn đã theo dõi",
            "hẹn gặp lại các bạn",
            "video hấp dẫn",
            "thank you for watching",
            "please subscribe",
            "subtitles by",
            "không có tiếng nói",
            "không có âm thanh",
            "không nghe rõ",
            "không có từ nào",
            "im lặng",
        ]
        lower = text.lower().strip()
        for h in hallucination_keywords:
            if h in lower:
                return ""

        # Chuẩn hóa khoảng trắng
        text = re.sub(r"\s+", " ", text).strip().lower()
        return HybridSTT.normalize_vietnamese_command(text)

    @staticmethod
    def normalize_vietnamese_command(text: str) -> str:
        """
        Chuẩn hóa các biến thể phát âm tiếng Việt thường gặp từ STT sang câu lệnh chuẩn:
        - Đồng âm vùng miền (chộp / chục / chộp ảnh -> chụp ảnh)
        - Từ hủy (huỷ / thui / thôi / thoát -> hủy)
        - Từ hỏi giờ (mấy h -> mấy giờ)
        - Từ thời tiết (thời tiếc -> thời tiết)
        - Từ hỏi ngày lễ (mấy ngày nữa / bao lâu nữa -> còn bao nhiêu ngày nữa)
        """
        if not text:
            return ""
        t = text.lower().strip()

        # 1. Chụp ảnh / Camera variants
        t = re.sub(r"\b(chộp|chục)\s+(ảnh|hình)\b", r"chụp \2", t)
        if t in ["chộp", "chục", "chụp", "chộp hình", "chục hình", "chộp đi", "chụp nà", "chụp nè", "chộp ảnh"]:
            return "chụp ảnh"

        # 2. Hủy bỏ / Thoát
        if t in ["huỷ", "thui", "thôi nha", "thôi nhé", "ngưng", "dừng", "hủy bỏ", "thoát"]:
            return "hủy"

        # 3. Thời tiết
        t = re.sub(r"\bthời tiếc\b", "thời tiết", t)

        # 4. Giờ giấc
        t = re.sub(r"\bmấy h\b", "mấy giờ", t)
        t = re.sub(r"\bbây giờ là mấy h\b", "bây giờ là mấy giờ", t)

        # 5. Đếm ngày lễ
        t = re.sub(r"\bmấy ngày nữa\b", "còn bao nhiêu ngày nữa", t)
        t = re.sub(r"\bbao lâu nữa\b", "còn bao nhiêu ngày nữa", t)

        return t

    def _transcribe_groq(self, wav_bytes: bytes) -> Optional[str]:
        """Gửi audio lên Groq Whisper Large v3 (Độ trễ ~0.25s)"""
        if not HAS_REQUESTS or not self.groq_api_key:
            return None

        url = "https://api.groq.com/openai/v1/audio/transcriptions"
        headers = {
            "Authorization": f"Bearer {self.groq_api_key}"
        }
        files = {
            "file": ("speech.wav", wav_bytes, "audio/wav")
        }
        data = {
            "model": "whisper-large-v3",
            "language": "vi",
            "temperature": "0.0",
            "response_format": "json"
        }

        try:
            resp = requests.post(url, headers=headers, files=files, data=data, timeout=1.8)
            if resp.status_code == 200:
                result = resp.json()
                raw_text = result.get("text", "")
                return self.clean_transcription(raw_text)
            else:
                print(f"[⚠️ Groq STT] Lỗi HTTP {resp.status_code}: {resp.text}")
                return None
        except Exception as e:
            print(f"[⚠️ Groq STT] Kết nối thất bại: {e}")
            return None

    def _transcribe_google_web(self, samples: np.ndarray, sample_rate: int = 16000) -> Optional[str]:
        """Sử dụng Google Web Speech API (Miễn phí, không cần API Key, phản hồi ~0.7s)"""
        if not HAS_SPEECH_RECOGNITION or not self.sr_recognizer:
            return None

        try:
            int16_data = (np.clip(samples, -1.0, 1.0) * 32767.0).astype(np.int16)
            audio = sr.AudioData(int16_data.tobytes(), sample_rate, 2)

            # Hook chuyển đổi sang FLAC thông qua FFmpeg trong bộ nhớ RAM
            def _get_flac():
                cmd = [
                    "ffmpeg", "-loglevel", "quiet",
                    "-f", "s16le", "-ar", str(sample_rate), "-ac", "1",
                    "-i", "pipe:0", "-f", "flac", "pipe:1"
                ]
                p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                flac_out, _ = p.communicate(audio.get_raw_data())
                return flac_out

            audio.get_flac_data = lambda convert_rate=None, convert_width=None: _get_flac()

            raw_text = self.sr_recognizer.recognize_google(audio, language="vi-VN")
            return self.clean_transcription(raw_text)
        except sr.UnknownValueError:
            # Không phát hiện giọng nói rõ ràng
            return None
        except Exception as e:
            # Lỗi mạng hoặc kết nối
            return None

    def _transcribe_gemini(self, wav_bytes: bytes) -> Optional[str]:
        """Gửi audio lên Google Gemini Flash Lite để chuyển thành văn bản tiếng Việt"""
        if not self.gemini_client or not HAS_GENAI:
            return None

        models_to_try = [
            "gemini-2.0-flash-lite",
            "gemini-2.0-flash",
            "gemini-1.5-flash"
        ]

        prompt = (
            "Chép lại chính xác từng từ tiếng Việt được nói trong đoạn âm thanh này. "
            "Chỉ trả lời câu văn bản tiếng Việt duy nhất, không thêm giải thích, không thêm dấu ngoặc kép hay tiền tố."
        )

        for model_name in models_to_try:
            try:
                response = self.gemini_client.models.generate_content(
                    model=model_name,
                    contents=[
                        types.Part.from_bytes(data=wav_bytes, mime_type="audio/wav"),
                        prompt
                    ],
                    config=types.GenerateContentConfig(
                        temperature=0.0,
                        max_output_tokens=80
                    )
                )
                if response and response.text:
                    return self.clean_transcription(response.text)
            except Exception:
                continue

        return None

    def transcribe_samples(
        self,
        samples: np.ndarray,
        sample_rate: int = 16000
    ) -> Tuple[str, float]:
        """
        Nhận dạng mảng âm thanh giọng nói (numpy float32/int16).
        Tự động thực hiện:
        1. Peak Normalization (bù âm lượng).
        2. Thử Cloud STT (Groq -> Google Web Speech -> Gemini).
        3. Tự động Fallback sang Local STT (Zipformer-30M) nếu Cloud gặp sự cố hoặc offline.
        
        Returns:
            (văn_bản_tiếng_việt, thời_gian_xử_lý_giây)
        """
        if len(samples) == 0:
            return "", 0.0

        # Chuẩn hóa về float32 [-1.0, 1.0]
        if samples.dtype == np.int16:
            samples = samples.astype(np.float32) / 32768.0
        elif samples.dtype != np.float32:
            samples = samples.astype(np.float32)

        if samples.ndim > 1:
            samples = samples.squeeze()

        # 1. Áp dụng Peak Normalization (bù âm cho mic nhỏ)
        samples = self.apply_peak_normalization(samples, target_peak=0.85, max_scale=5.0)
        audio_dur = len(samples) / float(sample_rate)

        start_t = time.perf_counter()

        # 2. Chế độ cưỡng chế Local STT
        if self.provider == "local":
            if self.local_stt and self.local_stt.is_ready:
                text, lat = self.local_stt.transcribe_samples(samples, sample_rate)
                return self.clean_transcription(text), lat
            return "", 0.0

        # Chuyển đổi thành WAV bytes cho các Cloud APIs
        wav_bytes = self.samples_to_wav_bytes(samples, sample_rate)

        # 3. Ưu tiên 1: Groq Whisper Large v3 (Nhanh nhất ~0.25s nếu có key)
        if (self.provider in ["auto", "groq"]) and self.groq_api_key:
            groq_text = self._transcribe_groq(wav_bytes)
            if groq_text:
                lat = time.perf_counter() - start_t
                print(f"[⚡ Groq STT] {audio_dur:.2f}s -> {lat:.3f}s | '{groq_text}'")
                return groq_text, lat

        # 4. Ưu tiên 2: Google Web Speech API (Miễn phí, không cần key, ~0.7s)
        if self.provider in ["auto", "google"]:
            google_text = self._transcribe_google_web(samples, sample_rate)
            if google_text:
                lat = time.perf_counter() - start_t
                print(f"[🌐 Google STT] {audio_dur:.2f}s -> {lat:.3f}s | '{google_text}'")
                return google_text, lat

        # 5. Ưu tiên 3: Gemini Audio STT (CHỈ gọi khi cấu hình STT_PROVIDER=gemini để bảo tồn Token)
        if (self.provider == "gemini") and self.gemini_client:
            gemini_text = self._transcribe_gemini(wav_bytes)
            if gemini_text:
                lat = time.perf_counter() - start_t
                print(f"[✨ Gemini STT] {audio_dur:.2f}s -> {lat:.3f}s | '{gemini_text}'")
                return gemini_text, lat

        # 6. Fallback sang Local STT (Zipformer-30M) khi Cloud mất kết nối hoặc offline
        if self.local_stt and self.local_stt.is_ready:
            print(f"[🔄 HybridSTT] Chuyển tiếp sang Local Zipformer-30M (Offline Fallback)...")
            text, lat = self.local_stt.transcribe_samples(samples, sample_rate)
            clean_text = self.clean_transcription(text)
            return clean_text, lat

        print("[❌ HybridSTT] Không có engine STT nào hoạt động khả dụng.")
        return "", 0.0

    def transcribe_wav(self, wav_path: str) -> Tuple[str, float]:
        """Nhận dạng file WAV trên đĩa"""
        if not os.path.exists(wav_path):
            print(f"[!] Không tìm thấy file âm thanh: {wav_path}")
            return "", 0.0

        try:
            with wave.open(wav_path, "rb") as wf:
                sample_rate = wf.getframerate()
                num_frames = wf.getnframes()
                raw_data = wf.readframes(num_frames)
                samples = np.frombuffer(raw_data, dtype=np.int16).astype(np.float32) / 32768.0

            return self.transcribe_samples(samples, sample_rate)
        except Exception as e:
            print(f"[❌ HybridSTT] Lỗi đọc file wav: {e}")
            return "", 0.0


# Singleton Instance
_hybrid_stt_instance: Optional[HybridSTT] = None

def get_stt_engine(provider: Optional[str] = None) -> HybridSTT:
    """Trả về Singleton instance của HybridSTT"""
    global _hybrid_stt_instance
    if _hybrid_stt_instance is None or (provider is not None and _hybrid_stt_instance.provider != provider):
        _hybrid_stt_instance = HybridSTT(provider=provider)
    return _hybrid_stt_instance


if __name__ == "__main__":
    print("=== KIỂM THỬ HYBRID STT SERVICE ===")
    engine = get_stt_engine()
    test_wav = os.path.join(PROJECT_ROOT, "test", "last_command.wav")
    if os.path.exists(test_wav):
        print(f"[+] Kiểm thử nhận diện với tệp: {test_wav}")
        text, dur = engine.transcribe_wav(test_wav)
        print(f"[+] Kết quả cuối cùng: '{text}' (thời gian: {dur:.3f}s)")
    else:
        print("[!] Không tìm thấy tệp test/last_command.wav để thử nghiệm.")


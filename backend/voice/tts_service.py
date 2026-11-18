"""
====================================================================
           TEXT-TO-SPEECH (TTS) SERVICE — VIETNAMESE
====================================================================
Hệ thống chuyển đổi văn bản thành giọng nói tiếng Việt cho Gương Thông Minh:
1. Engine: Google Translate TTS (gTTS vi) tự nhiên, phát âm chuẩn tiếng Việt.
2. Bộ đệm thông minh (Smart Audio Cache): Lưu trữ các câu lệnh quen thuộc
   dưới dạng file .mp3 bằng mã băm MD5 để phát tức thì trong ~0.001s.
3. Chống dội âm (Echo Prevention): Tự động phối hợp với AudioRecorder để
   tạm khóa micro khi gương đang nói, chống vòng lặp tự thu tiếng mình.
4. Trình phát âm thanh: Ưu tiên mpv / ffplay / cvlc đa nền tảng.
====================================================================
"""

import asyncio
import hashlib
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from typing import Optional, Callable

# Đảm bảo UTF-8
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))

# Thư mục lưu cache các tệp giọng nói
DEFAULT_CACHE_DIR = os.path.join(PROJECT_ROOT, "data", "tts_cache")

# Kiểm tra thư viện gTTS
try:
    from gtts import gTTS
    HAS_GTTS = True
except ImportError:
    HAS_GTTS = False
    gTTS = None


def clean_text_for_speech(text: str) -> str:
    """Làm sạch văn bản, loại bỏ markdown, emoji và ký tự đặc biệt để phát âm mượt mà"""
    if not text:
        return ""
    t = text
    # Xóa link markdown [Tiêu đề](url) -> Tiêu đề
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", t)
    # Xóa định dạng markdown: **in đậm**, *in nghiêng*, `code`
    t = re.sub(r"\*\*([^*]+)\*\*", r"\1", t)
    t = re.sub(r"\*([^*]+)\*", r"\1", t)
    t = re.sub(r"`([^`]+)`", r"\1", t)
    # Xóa URL trần
    t = re.sub(r"https?://\S+", "", t)
    # Xóa emoji và ký tự biểu tượng
    t = re.sub(r"[\U00010000-\U0010ffff]", "", t)
    # Xóa các gạch đầu dòng bullet
    t = re.sub(r"^\s*[-•✦★*]\s*", "", t, flags=re.M)
    # Xóa dấu ngoặc nhọn, ngoặc vuông thừa
    t = re.sub(r"[\[\]{}<>]", " ", t)
    # Chuẩn hóa khoảng trắng
    t = re.sub(r"\s+", " ", t).strip()
    return t


class TTSService:
    """Service chuyển đổi văn bản thành giọng nói tiếng Việt"""

    def __init__(self, cache_dir: Optional[str] = None):
        self.cache_dir = cache_dir or DEFAULT_CACHE_DIR
        os.makedirs(self.cache_dir, exist_ok=True)

        self.mic = None  # Sẽ được gán từ AudioRecorder
        self._current_process: Optional[subprocess.Popen] = None
        self._lock = threading.RLock()
        self.is_enabled = os.getenv("TTS_ENABLED", "true").lower() in ("true", "1", "yes")

        # Tìm trình phát âm thanh sẵn có trên hệ thống
        self.player_cmd = self._find_audio_player()
        if self.player_cmd:
            print(f"[🔊 TTS Service] Đã kích hoạt hệ thống giọng nói tiếng Việt (Trình phát: {self.player_cmd[0]})")
        else:
            print("[⚠️ TTS Service] Không tìm thấy mpv / ffplay / cvlc trên máy. TTS sẽ tạm tắt âm thanh.")

    def set_mic(self, mic):
        """Liên kết với Microphone để tự động khóa mic khi gương nói"""
        self.mic = mic

    @staticmethod
    def _find_audio_player() -> Optional[list]:
        """Tự động tìm kiếm player âm thanh khả dụng trong Linux"""
        if shutil.which("mpv"):
            return ["mpv", "--no-video", "--really-quiet"]
        if shutil.which("ffplay"):
            return ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet"]
        if shutil.which("cvlc"):
            return ["cvlc", "--play-and-exit", "-q"]
        return None

    def _generate_audio_file(self, clean_text: str) -> Optional[str]:
        """Tạo file âm thanh MP3 từ text hoặc lấy từ cache"""
        if not clean_text or not HAS_GTTS:
            return None

        # Tính toán hash md5 làm tên file cache
        text_hash = hashlib.md5(clean_text.strip().lower().encode("utf-8")).hexdigest()
        cache_path = os.path.join(self.cache_dir, f"{text_hash}.mp3")

        # Nếu đã có trong cache -> Dùng ngay tức thì (0.001s, 100% offline)
        if os.path.exists(cache_path) and os.path.getsize(cache_path) > 1000:
            return cache_path

        temp_path = cache_path + ".tmp"
        try:
            tts = gTTS(text=clean_text, lang="vi", slow=False)
            tts.save(temp_path)
            os.replace(temp_path, cache_path)
            return cache_path
        except Exception as e:
            print(f"[⚠️ TTS Service] Không thể tạo âm thanh cho câu nói: {e}")
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
            return None

    def speak(self, text: str, wait: bool = False, on_finish: Optional[Callable] = None):
        """
        Phát giọng nói tiếng Việt cho câu văn bản.
        Args:
            text: Văn bản cần đọc
            wait: Nếu True, chờ đọc xong mới return. Nếu False, đọc bất đồng bộ trong luồng riêng.
            on_finish: Callback sau khi đọc xong.
        """
        if not self.is_enabled or not text or not self.player_cmd:
            if on_finish:
                try:
                    on_finish()
                except Exception:
                    pass
            return

        clean_text = clean_text_for_speech(text)
        if not clean_text:
            return

        def _worker():
            with self._lock:
                # Dừng âm thanh đang phát trước đó nếu có
                if self._current_process and self._current_process.poll() is None:
                    try:
                        self._current_process.terminate()
                        self._current_process.wait(timeout=0.2)
                    except Exception:
                        pass

                audio_file = self._generate_audio_file(clean_text)
                if not audio_file or not os.path.exists(audio_file):
                    if on_finish:
                        try:
                            on_finish()
                        except Exception:
                            pass
                    return

                # 1. KHÓA MICROPHONE để chống thu ngược âm thanh gương nói (Acoustic Echo Prevention)
                if self.mic and hasattr(self.mic, "pause_for_tts"):
                    try:
                        self.mic.pause_for_tts()
                    except Exception:
                        pass

                try:
                    cmd = self.player_cmd + [audio_file]
                    self._current_process = subprocess.Popen(
                        cmd,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                    self._current_process.wait()
                except Exception as ex:
                    print(f"[!] Lỗi khi phát âm thanh TTS: {ex}")
                finally:
                    # Đợi một khoảng ngắn (0.35s) để tiếng vang trong phòng tan hết rồi mới mở lại micro
                    time.sleep(0.35)
                    if self.mic and hasattr(self.mic, "resume_after_tts"):
                        try:
                            self.mic.resume_after_tts(guard_seconds=0.35)
                        except Exception:
                            pass

                    if on_finish:
                        try:
                            on_finish()
                        except Exception:
                            pass

        if wait:
            _worker()
        else:
            threading.Thread(target=_worker, daemon=True).start()

    async def speak_async(self, text: str):
        """Phương thức bất đồng bộ cho asyncio"""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self.speak, text, True)


# Singleton Instance
_tts_instance: Optional[TTSService] = None

def get_tts_engine() -> TTSService:
    """Trả về Singleton instance của TTSService"""
    global _tts_instance
    if _tts_instance is None:
        _tts_instance = TTSService()
    return _tts_instance


if __name__ == "__main__":
    print("=== KIỂM THỬ TTS SERVICE TIẾNG VIỆT ===")
    tts = get_tts_engine()
    sample = "Chào bạn! Tôi là trợ lý AI trên gương thông minh Magic Mirror."
    print(f"[+] Đang phát thử: '{sample}'")
    tts.speak(sample, wait=True)
    print("[+] Kiểm thử hoàn tất thành công!")

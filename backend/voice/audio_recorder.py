"""
====================================================================
       AUDIO RECORDER & REAL-TIME RMS VOLUME STREAMER
====================================================================
Quản lý Microphone và Luồng Âm Thanh Thời Gian Thực:
1. Thu âm từ Microphone (16kHz, mono, float32/int16) qua sounddevice.
2. Đo độ lớn biên độ hiệu dụng RMS thời gian thực và phát sóng SiriWave
   vào WebSocket (:8085) mỗi ~45ms với dải giá trị [0.0 -> 1.0].
3. Đệm khung âm thanh (Audio Buffer) phục vụ cho:
   - Bộ nhận diện từ khóa Wakeword ("Hey mirror").
   - Bộ cắt khoảng lặng Silero VAD.
   - Bộ nhận dạng giọng nói tiếng Việt Zipformer-30M Local STT.
====================================================================
"""

from collections import deque
from datetime import datetime
import os
import shutil
import sys
import threading
import time
from typing import Callable, Optional, List, Tuple
import numpy as np

# Đảm bảo UTF-8
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Thư viện SoundDevice
try:
    import sounddevice as sd
    HAS_SOUNDDEVICE = True
except ImportError:
    sd = None
    HAS_SOUNDDEVICE = False

from backend.voice.stt_service import get_stt_engine, HybridSTT
from backend.voice.local_stt import get_local_stt
from backend.voice.wakeword import get_wakeword_detector, WakeWordDetector


def render_bar(val: float, max_val: float = 1.0, length: int = 12) -> str:
    """Vẽ thanh tiến trình ASCII trực quan theo tỷ lệ giá trị"""
    if max_val <= 0:
        return "░" * length
    ratio = min(1.0, max(0.0, float(val) / float(max_val)))
    filled = int(round(length * ratio))
    return "█" * filled + "░" * (length - filled)


class AudioRecorder:
    """
    Bộ thu âm Microphone và phát biên độ sóng SiriWave thời gian thực,
    kết hợp nhận diện từ khóa 'Hey Mirror' (Wakeword) và STT tiếng Việt.
    """

    def __init__(
        self,
        on_amplitude_callback: Optional[Callable[[float], None]] = None,
        on_speech_detected_callback: Optional[Callable[[str], None]] = None,
        on_wakeword_detected_callback: Optional[Callable[[float], None]] = None,
        device_index: Optional[int] = None,
        sample_rate: int = 16000,
        block_size: int = 1280,
        sensitivity: float = 12.0,
        enable_stt: bool = True,
        enable_wakeword: bool = True,
        voice_threshold: float = 0.025,
        silence_timeout: float = 0.80,
        min_speech_duration: float = 0.20,
        max_speech_duration: float = 6.0,
        enable_live_display: bool = True
    ):
        """
        Args:
            on_amplitude_callback: Hàm nhận giá trị volume [0.0 - 1.0] để phát ra sóng Siri
            on_speech_detected_callback: Hàm nhận văn bản tiếng Việt sau khi STT dịch xong
            device_index: Index của micro (nếu để None sẽ lấy micro mặc định của hệ điều hành)
            sample_rate: Tần số mẫu (16000 Hz chuẩn cho ASR / Zipformer / Whisper)
            block_size: Kích thước block thu âm (1024 mẫu ~64ms)
            sensitivity: Hệ số khuếch đại biên độ cho sóng SiriWave nhảy múa đẹp
            enable_stt: Bật/tắt tự động chuyển giọng nói thành văn bản
        """
        self.on_amplitude_callback = on_amplitude_callback
        self.on_speech_detected_callback = on_speech_detected_callback
        self.on_wakeword_detected_callback = on_wakeword_detected_callback
        self.device_index = device_index
        if self.device_index is None:
            env_dev = os.getenv("MIC_DEVICE_INDEX")
            try:
                self.device_index = int(env_dev) if env_dev is not None else None
            except Exception:
                self.device_index = None

        # Tự động ghim vào Micro USB phần cứng thật để tránh bị Loa Bluetooth cướp quyền Default Input
        if self.device_index is None and HAS_SOUNDDEVICE:
            try:
                devices = sd.query_devices()
                for idx, dev in enumerate(devices):
                    if dev.get("max_input_channels", 0) > 0:
                        name_lower = dev.get("name", "").lower()
                        if any(k in name_lower for k in ["usb", "composite", "webcam", "camera"]):
                            self.device_index = idx
                            break
            except Exception:
                pass

        self.sample_rate = sample_rate
        self.block_size = block_size
        self.sensitivity = sensitivity
        self.enable_stt = enable_stt
        self.enable_wakeword = enable_wakeword
        env_vth = os.getenv("VAD_VOICE_THRESHOLD")
        self.voice_threshold = float(env_vth) if env_vth is not None else voice_threshold
        self.silence_timeout = silence_timeout
        self.min_speech_duration = min_speech_duration
        self.max_speech_duration = max_speech_duration

        # Khuếch đại tiền xử lý phần mềm (Software Pre-amp Gain)
        env_gain = os.getenv("MIC_SOFTWARE_GAIN")
        try:
            self.software_gain = float(env_gain) if env_gain is not None else 2.2
        except Exception:
            self.software_gain = 2.2

        # Bộ nhận diện từ khóa "Hey Mirror"
        self.wakeword_detector = get_wakeword_detector() if self.enable_wakeword else None

        self.is_running = False
        self.stream: Optional[sd.InputStream] = None
        self._last_emit_time = 0.0
        self._last_callback_time = time.time()
        self._lock = threading.RLock()

        # VAD & Speech Buffer
        self.is_speaking = False
        self.speech_buffer: List[np.ndarray] = []
        self.preroll_buffer = deque(maxlen=6)  # Lưu trước ~0.48s âm thanh để không bị mất chữ đầu
        self.silence_start_time: Optional[float] = None
        self.speech_start_time: Optional[float] = None
        self.ambient_noise_level: float = 0.005
        self._is_transcribing = False
        self._wake_ignore_until: float = 0.0

        # Cổng kiểm soát lắng nghe: Nếu bật Wakeword thì CHỈ lắng nghe sau khi hô 'Hey Mirror'
        self.is_listening_for_command = not self.enable_wakeword
        self.listen_start_time = 0.0

        # Chế độ ghi âm rảnh tay liên tục (khi tạo dáng chụp ảnh / Photo Mode)
        self.is_continuous_listening: bool = False
        self.continuous_timeout: float = 60.0
        self.is_muted_for_tts: bool = False

        # Biến trạng thái hiển thị thanh tiến trình trực quan
        self.latest_rms: float = 0.0
        self.latest_score: float = 0.0
        self.session_count: int = 0
        self._last_display_time: float = 0.0
        self.enable_live_display: bool = enable_live_display

        # Bộ lọc thông cao (High-pass filter) 80Hz cắt bỏ tiếng ù nền, rung bàn, quạt tản nhiệt
        try:
            from scipy import signal
            self._hp_b, self._hp_a = signal.butter(2, 80.0 / (self.sample_rate / 2.0), btype="high")
            self._hp_zi = signal.lfilter_zi(self._hp_b, self._hp_a)
            self._has_filter = True
        except Exception:
            self._has_filter = False

    def start(self) -> bool:
        """Bắt đầu thu âm và gửi biên độ sóng âm"""
        if not HAS_SOUNDDEVICE:
            print("[❌ AudioRecorder] Chưa cài đặt sounddevice. Chạy: pip install sounddevice")
            return False

        if self.is_running:
            return True

        try:
            self.stream = sd.InputStream(
                samplerate=self.sample_rate,
                blocksize=self.block_size,
                device=self.device_index,
                channels=1,
                dtype="float32",
                callback=self._audio_callback
            )
            self.stream.start()
            self.is_running = True
            print(f"[🎤 AudioRecorder] Micro đã mở (SampleRate: {self.sample_rate}Hz, Device: {self.device_index or 'Default'})")
            return True
        except Exception as e:
            print(f"[⚠️ AudioRecorder] Chưa mở được Microphone ({e}). Khi cắm Micro vào Pi/máy tính, hệ thống sẽ tự động hoạt động.")
            self.is_running = False
            return False

    def stop(self):
        """Dừng luồng thu âm"""
        self.is_running = False
        if self.stream is not None:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception:
                pass
            self.stream = None
        print("[🎤 AudioRecorder] Đã dừng thu âm micro.")

    def flush_speech_buffer(self, ignore_duration: float = 0.65):
        """Xóa sạch bộ đệm âm thanh VAD để bỏ qua âm thanh từ khóa đánh thức 'Hey Mirror'"""
        with self._lock:
            self.is_speaking = False
            self.speech_buffer.clear()
            self.preroll_buffer.clear()
            self.silence_start_time = None
            self.speech_start_time = None
            self._wake_ignore_until = time.time() + ignore_duration

    def start_listening(self, timeout_sec: float = 7.0):
        """Kích hoạt trạng thái lắng nghe câu lệnh (từ Wakeword, Console hoặc UI)"""
        with self._lock:
            self.is_listening_for_command = True
            self.listen_start_time = time.time()
            self.is_speaking = False
            self.speech_buffer.clear()
            self.preroll_buffer.clear()
            self.silence_start_time = None
            self.speech_start_time = None
            self._wake_ignore_until = time.time() + 0.65

    def start_photo_mode(self, timeout_sec: float = 60.0):
        """Kích hoạt trạng thái lắng nghe liên tục phục vụ cho Chế độ Chụp ảnh / Tạo dáng"""
        self.start_continuous_listening(timeout_sec=timeout_sec)

    def stop_photo_mode(self):
        """Dừng trạng thái lắng nghe liên tục khi chụp ảnh xong hoặc hủy chụp"""
        self.stop_continuous_listening()

    def start_continuous_listening(self, timeout_sec: float = 60.0):
        """Mở cổng micro lắng nghe liên tục không cần hô lại Wakeword (Hey Mirror)"""
        with self._lock:
            self.is_continuous_listening = True
            self.continuous_timeout = timeout_sec
            self.is_listening_for_command = True
            self.listen_start_time = time.time()
            self.is_speaking = False
            self.speech_buffer.clear()
            self.preroll_buffer.clear()
            self.silence_start_time = None
            self.speech_start_time = None
            self._wake_ignore_until = 0.0

    def stop_continuous_listening(self):
        """Tắt lắng nghe liên tục và trở về trạng thái Wakeword mặc định"""
        with self._lock:
            self.is_continuous_listening = False
            self.is_listening_for_command = not self.enable_wakeword
            self.is_speaking = False
            self.speech_buffer.clear()
            self.preroll_buffer.clear()
            self.silence_start_time = None
            self.speech_start_time = None
            self._wake_ignore_until = 0.0

    def pause_for_tts(self):
        """Tạm ngắt microphone khi gương đang phát giọng nói qua loa (chống dội âm)"""
        with self._lock:
            self.is_muted_for_tts = True
            self.is_speaking = False
            self.speech_buffer.clear()
            self.preroll_buffer.clear()
            self.silence_start_time = None
            self.speech_start_time = None

    def resume_after_tts(self, guard_seconds: float = 0.35):
        """Mở lại microphone sau khi gương nói xong và âm vang trong phòng đã dứt"""
        with self._lock:
            self.is_muted_for_tts = False
            self._wake_ignore_until = time.time() + guard_seconds
            if self.is_continuous_listening:
                self.is_listening_for_command = True

    def _render_live_status(self, rms: float, score: float, now: float):
        """Vẽ thanh trạng thái thời gian thực trên đúng 1 dòng duy nhất (chống trôi/xuống dòng)"""
        if not self.enable_live_display or self._is_transcribing or not sys.stdout.isatty():
            return

        vu_bar = render_bar(rms * 10.0, max_val=1.0, length=8)

        if getattr(self, "is_muted_for_tts", False):
            line = f"🔊 [GƯƠNG ĐANG NÓI...] Micro tạm ngắt chống vọng tiếng | Mic:[{vu_bar}]"
        elif not self.is_listening_for_command and not self.is_continuous_listening:
            pct = min(100, int(score * 100))
            line = f"🎙️ [CHỜ TỪ KHÓA] Mic:[{vu_bar}] | Score:{pct:2d}% | Ồn:{self.ambient_noise_level:.2f}"
        else:
            dyn_thresh = min(0.065, max(self.voice_threshold, self.ambient_noise_level + 0.015))
            if self.is_speaking:
                if self.silence_start_time is not None:
                    silence_dur = now - self.silence_start_time
                    silence_bar = render_bar(silence_dur, max_val=self.silence_timeout, length=6)
                    line = f"🎙️ [LẶNG {silence_dur:2.1f}s:{silence_bar}] Đợi dứt câu... Mic:[{vu_bar}]"
                else:
                    tag = "CHỤP ẢNH" if self.is_continuous_listening else "CÂU LỆNH"
                    line = f"🎙️ [ĐANG NÓI - {tag}] Mic:[{vu_bar}] RMS:{rms:.3f}"
            else:
                max_t = self.continuous_timeout if self.is_continuous_listening else 7.0
                remain = max(0.0, max_t - (now - self.listen_start_time))
                if self.is_continuous_listening:
                    line = f"📸 [CHỜ LỆNH {remain:2.0f}s] Nói 'Chụp' / 'Hủy' | Mic:[{vu_bar}]"
                else:
                    line = f"👂 [ĐANG LẮNG NGHE {remain:2.0f}s] Chờ bạn nói... | Mic:[{vu_bar}]"

        cols = shutil.get_terminal_size((80, 20)).columns
        if len(line) >= cols:
            line = line[:cols - 2]

        sys.stdout.write(f"\r\033[K{line}")
        sys.stdout.flush()

    def _audio_callback(self, indata, frames, time_info, status):
        """Callback nhận luồng âm thanh theo thời gian thực từ driver âm thanh"""
        if not self.is_running:
            return

        now = time.time()
        self._last_callback_time = now

        try:
            # 1. Thu nhận tín hiệu thô từ microphone
            audio_chunk = indata[:, 0].copy()

            # Lọc bỏ ù nền < 80Hz (tiếng quạt, rung bàn)
            if getattr(self, "_has_filter", False):
                try:
                    from scipy import signal
                    audio_chunk, self._hp_zi = signal.lfilter(self._hp_b, self._hp_a, audio_chunk, zi=self._hp_zi)
                except Exception:
                    pass

            # Khuếch đại phần mềm (Software Gain)
            if self.software_gain != 1.0:
                audio_chunk = np.clip(audio_chunk * self.software_gain, -1.0, 1.0)

            # Đo độ lớn biên độ RMS
            rms = np.sqrt(np.mean(audio_chunk**2))
            self.latest_rms = float(rms)

            # Cập nhật mức ồn môi trường nền (noise floor) có trần chặn tối đa để tránh bị nhạc/tiếng ồn làm điếc mic
            if not self.is_speaking:
                raw_noise = self.ambient_noise_level * 0.95 + float(rms) * 0.05
                self.ambient_noise_level = min(0.075, raw_noise)

            # Chuẩn hóa âm lượng [0.0 - 1.0] gửi cho sóng SiriWave
            norm_amp = min(1.0, max(0.0, float(rms) * self.sensitivity))

            # Giảm tải: Bắn WebSocket mỗi ~45ms (khoảng 22 fps là cực kỳ mượt cho sóng đồ họa)
            if (now - self._last_emit_time) >= 0.045:
                self._last_emit_time = now
                if self.on_amplitude_callback:
                    try:
                        self.on_amplitude_callback(norm_amp)
                    except Exception:
                        pass

            # 2. Xử lý khi micro đang tạm khóa cho TTS phát loa (Echo Prevention)
            if getattr(self, "is_muted_for_tts", False):
                if self.enable_live_display and (now - self._last_display_time) >= 0.045:
                    self._last_display_time = now
                    self._render_live_status(float(rms), 0.0, now)
                return

            # 3. Xử lý nhận diện từ khóa đánh thức Wakeword ("Hey Mirror")
            if self.enable_wakeword and self.wakeword_detector and self.wakeword_detector.is_ready and not self.is_continuous_listening:
                try:
                    detected, score = self.wakeword_detector.process_chunk(audio_chunk)
                    self.latest_score = float(score)
                    if detected:
                        self.session_count += 1
                        time_str = datetime.now().strftime("%H:%M:%S")
                        dyn_thresh = min(0.065, max(self.voice_threshold, self.ambient_noise_level + 0.015))
                        sys.stdout.write("\r\033[K")
                        print(f"\n\n🔥 [{time_str}] [ĐÁNH THỨC THÀNH CÔNG #{self.session_count}] 'Hey Mirror' (Khớp {score*100:.1f}%)")
                        print(f"   🎙️ ➔ [ĐANG LẮNG NGHE CÂU LỆNH] (Ngưỡng VAD: {dyn_thresh:.3f} | Ồn phòng: {self.ambient_noise_level:.3f})")
                        # Ngay lập tức mở cổng lắng nghe câu lệnh và xóa sạch buffer cũ
                        self.start_listening(timeout_sec=7.0)
                        if self.on_wakeword_detected_callback:
                            try:
                                self.on_wakeword_detected_callback(score)
                            except Exception as cb_err:
                                print(f"[!] Lỗi callback wakeword: {cb_err}")
                except Exception:
                    pass

            # 3. Hiển thị thanh tiến trình trực quan
            if self.enable_live_display and (now - self._last_display_time) >= 0.045:
                self._last_display_time = now
                self._render_live_status(float(rms), float(self.latest_score), now)

            # 4. Xử lý VAD & Đệm câu nói để nhận dạng tiếng Việt
            if self.enable_stt and not self._is_transcribing:
                self._process_vad(audio_chunk, float(rms), now)

        except Exception as e:
            pass

    def _process_vad(self, chunk: np.ndarray, rms: float, now: float):
        """Thuật toán Voice Activity Detection (VAD) nhận diện người nói và ngắt câu"""
        # CỔNG BẢO VỆ: Nếu bật Wakeword nhưng chưa được đánh thức bằng 'Hey Mirror' và không ở chế độ chụp ảnh/nghe liên tục -> Không ghi âm!
        if self.enable_wakeword and not self.is_listening_for_command and not self.is_continuous_listening:
            return

        # Bỏ qua âm thanh trong thời gian hồi phục sau khi vừa hô từ khóa đánh thức (chỉ khi không ở chế độ chụp ảnh)
        if not self.is_continuous_listening and now < self._wake_ignore_until:
            self.is_speaking = False
            self.speech_buffer.clear()
            self.silence_start_time = None
            self.speech_start_time = None
            return

        dynamic_threshold = min(0.065, max(self.voice_threshold, self.ambient_noise_level + 0.015))

        if not self.is_speaking:
            # Đang trong khoảng lặng: lưu vào bộ nhớ đệm preroll
            self.preroll_buffer.append(chunk.copy())

            # Phát hiện bắt đầu có tiếng nói
            if rms > dynamic_threshold:
                self.is_speaking = True
                self.speech_start_time = now
                self.silence_start_time = None
                self.speech_buffer = list(self.preroll_buffer)
                self.speech_buffer.append(chunk.copy())
            else:
                timeout_limit = self.continuous_timeout if self.is_continuous_listening else 7.0
                # Nếu sau timeout_limit không nói gì -> Tự động khóa lại chờ 'Hey Mirror' tiếp theo
                if (now - self.listen_start_time) >= timeout_limit:
                    if self.is_continuous_listening:
                        self.is_continuous_listening = False
                    self.is_listening_for_command = not self.enable_wakeword
                    self.speech_buffer.clear()
                    self.is_speaking = False
                    self.silence_start_time = None
                    self.speech_start_time = None
                    if self.enable_wakeword:
                        time_str = datetime.now().strftime("%H:%M:%S")
                        sys.stdout.write("\r\033[K")
                        print(f"\n   ⏱️ [{time_str}] [HẾT GIỜ] Không nhận được câu lệnh nào.")
                        print("\n[✦ SẴN SÀNG] Đang chờ bạn nói 'Hey Mirror'...\n")
                    return
        else:
            # Đang trong quá trình nói
            self.speech_buffer.append(chunk.copy())
            speech_dur = now - (self.speech_start_time or now)

            # Ngưỡng phát hiện kết thúc câu nói: cho phép dứt câu ngay cả khi có nhạc nền nhỏ
            silence_thresh = min(dynamic_threshold * 0.85, max(self.voice_threshold * 0.88, self.ambient_noise_level + 0.007))

            if rms > silence_thresh:
                # Vẫn đang tiếp tục nói
                self.silence_start_time = None
            else:
                # Bắt đầu rơi vào khoảng lặng
                if self.silence_start_time is None:
                    self.silence_start_time = now
                elif (now - self.silence_start_time) >= self.silence_timeout:
                    # Đã im lặng vượt quá silence_timeout (~0.8s) -> Dứt câu!
                    if self.is_continuous_listening:
                        # Trong chế độ chụp ảnh: tiếp tục giữ cổng mở cho lần ra lệnh tiếp theo
                        self.is_listening_for_command = True
                        self.listen_start_time = now
                    else:
                        self.is_listening_for_command = not self.enable_wakeword

                    min_dur = 0.15 if self.is_continuous_listening else self.min_speech_duration
                    if speech_dur >= min_dur:
                        time_str = datetime.now().strftime("%H:%M:%S")
                        sys.stdout.write("\r\033[K")
                        print(f"\n   ✂️ [{time_str}] [NGẮT CÂU THÀNH CÔNG] Đã phát hiện {self.silence_timeout:.2f}s im lặng sau câu nói.")
                        self._trigger_stt(list(self.speech_buffer))
                    # Reset trạng thái
                    self.is_speaking = False
                    self.speech_buffer.clear()
                    self.silence_start_time = None
                    self.speech_start_time = None
                    return

            # Quá thời lượng tối đa cho phép
            if speech_dur >= self.max_speech_duration:
                if self.is_continuous_listening:
                    self.is_listening_for_command = True
                    self.listen_start_time = now
                else:
                    self.is_listening_for_command = not self.enable_wakeword

                min_dur = 0.15 if self.is_continuous_listening else self.min_speech_duration
                if speech_dur >= min_dur:
                    time_str = datetime.now().strftime("%H:%M:%S")
                    sys.stdout.write("\r\033[K")
                    print(f"\n   🛑 [{time_str}] [QUÁ THỜI LƯỢNG {self.max_speech_duration:.0f}s] Tự động ngắt câu lệnh để xử lý...")
                    self._trigger_stt(list(self.speech_buffer))
                self.is_speaking = False
                self.speech_buffer.clear()
                self.silence_start_time = None
                self.speech_start_time = None
                return

    def _trigger_stt(self, chunks: List[np.ndarray]):
        """Kích hoạt giải mã nhận dạng giọng nói trong luồng phụ (không làm nghẽn mic)"""
        if not chunks or self._is_transcribing:
            return

        self._is_transcribing = True

        def worker():
            try:
                full_audio = np.concatenate(chunks, axis=0)
                dur = len(full_audio) / self.sample_rate
                stt_engine = get_stt_engine()
                prov_name = getattr(stt_engine, 'provider', 'hybrid').upper()
                sys.stdout.write("\r\033[K")
                print(f"   ⏳ [1/2: STT] Đang giải mã {dur:.2f}s âm thanh qua Hybrid STT ({prov_name})...")
                if stt_engine.is_ready:
                    text, latency = stt_engine.transcribe_samples(full_audio, self.sample_rate)
                    if text:
                        # Lọc bỏ từ khóa đánh thức nếu còn sót ở đầu câu lệnh
                        for v in ["hey mirror", "hay mirror", "ê mirror", "ê mi rơ", "mirror"]:
                            if text.startswith(v):
                                text = text[len(v):].strip()
                        if text:
                            sys.stdout.write("\r\033[K")
                            print(f"   ✅ [STT Hoàn thành trong {latency:.3f}s]: \"{text.upper()}\"")
                            if self.on_speech_detected_callback:
                                try:
                                    self.on_speech_detected_callback(text, latency)
                                except TypeError:
                                    self.on_speech_detected_callback(text)
                        else:
                            sys.stdout.write("\r\033[K")
                            print(f"   ℹ️ [STT] Âm thanh chỉ chứa từ khóa đánh thức, đã bỏ qua.")
                            print("\n[✦ SẴN SÀNG] Đang chờ bạn nói 'Hey Mirror'...\n")
                    else:
                        sys.stdout.write("\r\033[K")
                        print(f"   ℹ️ [STT] Thu âm {dur:.2f}s nhưng không nhận diện được câu nói rõ ràng.")
                        print("\n[✦ SẴN SÀNG] Đang chờ bạn nói 'Hey Mirror'...\n")
            except Exception as e:
                sys.stdout.write("\r\033[K")
                print(f"\n[❌ AudioRecorder] Lỗi nhận diện giọng nói: {e}")
            finally:
                self._is_transcribing = False

        threading.Thread(target=worker, daemon=True).start()

# Định nghĩa bí danh tương thích cho mã nguồn cũ
RealMicrophone = AudioRecorder


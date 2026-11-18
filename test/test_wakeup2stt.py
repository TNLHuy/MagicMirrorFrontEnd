"""
====================================================================
      TEST WAKEUP2STT: KIỂM THỬ LUỒNG 'HEY MIRROR' ➔ VAD ➔ STT
====================================================================
Luồng hoạt động:
1. Trạng thái 1 [CHỜ TỪ KHÓA]: Liên tục lắng nghe 'Hey Mirror' qua openWakeWord.
2. Trạng thái 2 [KÍCH HOẠT]: Khi phát hiện từ khóa:
   - Xóa sạch âm thanh từ khóa 'Hey Mirror' khỏi bộ đệm.
   - Bắt đầu lắng nghe câu lệnh tiếp theo.
3. Trạng thái 3 [THU ÂM VAD]:
   - Tự động phát hiện khi bạn bắt đầu nói và dừng lại sau ~0.8s khoảng lặng.
   - Tự động hủy nếu sau 7.0s bạn không nói gì.
4. Trạng thái 4 [GIẢI MÃ STT]:
   - Gửi âm thanh câu lệnh vào Hybrid STT (Cloud ASR / Zipformer-30M).
   - In văn bản tiếng Việt nhận diện được.
   - Lưu tệp âm thanh vào: test/last_command.wav.
5. Quay lại Trạng thái 1 chờ lượt tiếp theo.
====================================================================
"""

import argparse
from collections import deque
from datetime import datetime
import os
import sys
import time
import wave
from typing import Optional, List, Tuple
import numpy as np

# Đảm bảo UTF-8
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Thêm thư mục gốc vào sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Tải cấu hình biến môi trường từ .env
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(PROJECT_ROOT, ".env"))
except ImportError:
    pass

from backend.voice.wakeword import get_wakeword_detector, WakeWordDetector
from backend.voice.stt_service import get_stt_engine, HybridSTT

try:
    import sounddevice as sd
    HAS_SOUNDDEVICE = True
except ImportError:
    sd = None
    HAS_SOUNDDEVICE = False


def get_available_input_devices() -> List[Tuple[int, str, int]]:
    """Lấy danh sách thiết bị micro"""
    if not HAS_SOUNDDEVICE:
        return []
    devices = []
    try:
        for idx, dev in enumerate(sd.query_devices()):
            max_in = dev.get("max_input_channels", 0)
            if max_in > 0:
                devices.append((idx, dev.get("name", f"Device #{idx}"), max_in))
    except Exception as e:
        print(f"[!] Lỗi khi quét thiết bị: {e}")
    return devices


def select_best_input_device(preferred_idx: Optional[int] = None) -> Optional[int]:
    """Chọn micro tối ưu"""
    if not HAS_SOUNDDEVICE:
        return None
    devices = get_available_input_devices()
    if not devices:
        return None

    if preferred_idx is not None:
        for idx, _, _ in devices:
            if idx == preferred_idx:
                return idx

    env_dev = os.getenv("MIC_DEVICE_INDEX")
    if env_dev is not None:
        try:
            env_idx = int(env_dev)
            for idx, _, _ in devices:
                if idx == env_idx:
                    return idx
        except Exception:
            pass

    for idx, name, _ in devices:
        if any(k in name.lower() for k in ["usb", "mic", "composite", "pipewire", "pulse", "default"]):
            return idx

    return devices[0][0]


def render_bar(val: float, max_val: float = 1.0, length: int = 14) -> str:
    ratio = min(1.0, max(0.0, val / max_val))
    filled = int(round(length * ratio))
    return "█" * filled + "░" * (length - filled)


def save_wav(filepath: str, audio_data: np.ndarray, sample_rate: int = 16000):
    int16_data = (np.clip(audio_data, -1.0, 1.0) * 32767.0).astype(np.int16)
    with wave.open(filepath, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(int16_data.tobytes())


def main():
    default_thresh = float(os.getenv("WAKEWORD_THRESHOLD", "0.65"))
    default_gain = float(os.getenv("MIC_SOFTWARE_GAIN", "2.2"))
    default_vad = float(os.getenv("VAD_VOICE_THRESHOLD", "0.055"))

    parser = argparse.ArgumentParser(description="Kiểm thử chuỗi Hey Mirror -> VAD -> STT Tiếng Việt")
    parser.add_argument("--device", type=int, default=None, help="Chỉ số index của micro")
    parser.add_argument("--threshold", type=float, default=default_thresh, help=f"Ngưỡng kích hoạt 'Hey Mirror' (mặc định {default_thresh:.2f})")
    parser.add_argument("--gain", type=float, default=default_gain, help=f"Hệ số khuếch đại tiền xử lý mic (mặc định {default_gain:.1f}x)")
    parser.add_argument("--vad-thresh", type=float, default=default_vad, help=f"Ngưỡng nhạy nhận diện giọng nói VAD (mặc định {default_vad:.3f})")
    parser.add_argument("--silence-timeout", type=float, default=0.80, help="Thời gian im lặng để ngắt câu (giây, mặc định 0.80)")
    parser.add_argument("--max-duration", type=float, default=8.0, help="Thời lượng câu lệnh tối đa (giây, mặc định 8.0)")
    parser.add_argument("--provider", type=str, default="auto", choices=["auto", "google", "groq", "gemini", "local"],
                        help="Bộ giải mã STT: auto (khuyên dùng), google, groq, gemini, local (Zipformer-30M)")
    parser.add_argument("--list-devices", action="store_true", help="Xem danh sách thiết bị micro rồi thoát")
    args = parser.parse_args()

    if not HAS_SOUNDDEVICE:
        print("[❌ LỖI] Chưa cài đặt sounddevice. Hãy chạy: pip install sounddevice")
        return

    if args.list_devices:
        devices = get_available_input_devices()
        print("\n📋 DANH SÁCH THIẾT BỊ MICROPHONE:")
        for idx, name, ch in devices:
            star = " ★ (Khuyên dùng)" if any(k in name.lower() for k in ["usb", "mic", "composite"]) else ""
            print(f"  [{idx:2d}] {name} (Kênh vào: {ch}){star}")
        return

    dev_idx = select_best_input_device(args.device)
    if dev_idx is None:
        print("[❌ LỖI] Không tìm thấy thiết bị Microphone nào đang kết nối!")
        return

    try:
        dev_info = sd.query_devices(dev_idx)
        dev_name = dev_info.get("name", f"Device #{dev_idx}")
    except Exception:
        dev_name = f"Device #{dev_idx}"

    # 1. Khởi tạo Wakeword
    print("⏳ [1/2] Đang nạp mô hình openWakeWord (Hey Mirror)...")
    ww_detector = get_wakeword_detector()
    if not ww_detector or not ww_detector.is_ready:
        print("[❌ LỖI] Không nạp được mô hình Wakeword.")
        return
    ww_detector.threshold = args.threshold
    ww_detector.reset()

    # 2. Khởi tạo STT
    print(f"⏳ [2/2] Đang nạp mô hình Hybrid STT (Chế độ: {args.provider.upper()})...")
    stt_engine = get_stt_engine(provider=args.provider)
    if not stt_engine or not stt_engine.is_ready:
        print("[❌ LỖI] Không nạp được STT Engine.")
        return

    SAMPLE_RATE = 16000
    CHUNK_SIZE = 1280
    test_dir = os.path.join(PROJECT_ROOT, "test")
    os.makedirs(test_dir, exist_ok=True)
    wav_path = os.path.join(test_dir, "last_command.wav")

    print(f"""
╔══════════════════════════════════════════════════════════════════════╗
║        🚀 TEST WAKEUP2STT — HEY MIRROR ➔ VAD ➔ STT TIẾNG VIỆT         ║
╠══════════════════════════════════════════════════════════════════════╣
║ • Microphone đang dùng : [{dev_idx}] {dev_name:<39}║
║ • Ngưỡng Hey Mirror    : {args.threshold*100:5.1f}% (Độ khớp)                        ║
║ • Tiền khuếch đại Gain : {args.gain:5.1f}x (Software Pre-amp)                 ║
║ • Ngưỡng nhạy VAD      : {args.vad_thresh:5.3f} (Phát hiện tiếng nói)             ║
║ • Bộ giải mã STT       : {args.provider.upper():<44}║
╠══════════════════════════════════════════════════════════════════════╣
║  👉 Bước 1: Nói "Hey Mirror" trước mic                               ║
║  👉 Bước 2: Khi thấy thông báo [ĐANG LẮNG NGHE], nói câu lệnh        ║
║  👉 Nhấn [Ctrl+C] để thoát                                           ║
╚══════════════════════════════════════════════════════════════════════╝
""")

    # Biến trạng thái State Machine
    STATE_WAIT_WAKE = 0
    STATE_LISTENING = 1
    current_state = STATE_WAIT_WAKE

    preroll_buffer = deque(maxlen=6)  # Lưu trước ~0.48s âm thanh
    speech_buffer = []
    is_speaking = False
    speech_start_time = None
    silence_start_time = None
    listen_start_time = 0.0
    wake_ignore_until = 0.0
    ambient_noise_level = 0.025
    current_dynamic_thresh = args.vad_thresh
    last_score = 0.0
    session_count = 0

    current_rms = 0.0
    current_score = 0.0

    def audio_callback(indata, frames, time_info, status):
        nonlocal current_rms, current_score, current_state, is_speaking
        nonlocal silence_start_time, speech_start_time, listen_start_time, wake_ignore_until
        nonlocal last_score, session_count, ambient_noise_level, current_dynamic_thresh

        now = time.time()
        chunk = indata[:, 0].copy()
        if args.gain != 1.0:
            chunk = np.clip(chunk * args.gain, -1.0, 1.0)

        rms = float(np.sqrt(np.mean(chunk**2)))
        current_rms = rms

        # -------------------------------------------------------------
        # TRẠNG THÁI 1: CHỜ TỪ KHÓA ĐÁNH THỨC 'HEY MIRROR'
        # -------------------------------------------------------------
        if current_state == STATE_WAIT_WAKE:
            # Liên tục học và thích ứng mức ồn môi trường thực tế của phòng
            ambient_noise_level = ambient_noise_level * 0.95 + rms * 0.05
            preroll_buffer.append(chunk)

            detected, score = ww_detector.process_chunk(chunk)
            current_score = float(score)

            if detected and now >= wake_ignore_until:
                last_score = score
                session_count += 1
                current_state = STATE_LISTENING
                listen_start_time = now
                # Đặt thời gian hồi phục 0.65s để bỏ qua đoạn đuôi của từ 'Hey Mirror'
                wake_ignore_until = now + 0.65
                speech_buffer.clear()
                preroll_buffer.clear()
                is_speaking = False
                speech_start_time = None
                silence_start_time = None
                ww_detector.reset()

                # Tự động tính toán ngưỡng nhạy VAD cao hơn mức ồn phòng
                current_dynamic_thresh = max(args.vad_thresh, ambient_noise_level * 1.55)

                time_str = datetime.now().strftime("%H:%M:%S")
                print(f"\n\n🔥 [{time_str}] [ĐÁNH THỨC THÀNH CÔNG #{session_count}] 'Hey Mirror' (Khớp {score*100:.1f}%)")
                print(f"   🎙️ ➔ [ĐANG LẮNG NGHE CÂU LỆNH] (Ngưỡng VAD: {current_dynamic_thresh:.3f} | Ồn phòng: {ambient_noise_level:.3f})")

        # -------------------------------------------------------------
        # TRẠNG THÁI 2: ĐANG LẮNG NGHE CÂU LỆNH (VAD & CẮT CÂU THÔNG MINH)
        # -------------------------------------------------------------
        elif current_state == STATE_LISTENING:
            current_score = 0.0

            # Bỏ qua âm thanh từ khóa 'Hey Mirror' trong 0.65s đầu
            if now < wake_ignore_until:
                return

            speech_buffer.append(chunk)

            # Ngưỡng bắt đầu nói và ngưỡng giữ nói (Hysteresis chống ngắt nhầm giữa từ)
            voice_start_thresh = current_dynamic_thresh
            voice_hold_thresh = current_dynamic_thresh * 0.70

            if not is_speaking:
                # Chưa bắt đầu nói: kiểm tra xem người dùng đã cất tiếng chưa
                if rms > voice_start_thresh:
                    is_speaking = True
                    speech_start_time = now
                    silence_start_time = None
                else:
                    # Cập nhật nhẹ mức ồn phòng khi đang chờ
                    ambient_noise_level = ambient_noise_level * 0.98 + rms * 0.02
                    current_dynamic_thresh = max(args.vad_thresh, ambient_noise_level * 1.55)
            else:
                # Đang trong câu nói: kiểm tra xem còn nói hay đã rơi vào khoảng lặng
                speech_dur = now - (speech_start_time or now)

                if rms > voice_hold_thresh:
                    # Vẫn đang nói rõ ràng -> Reset bộ đếm khoảng lặng
                    silence_start_time = None
                else:
                    # Âm lượng đã tụt xuống dưới ngưỡng giữ nói -> Bắt đầu đếm khoảng lặng
                    if silence_start_time is None:
                        silence_start_time = now
                    elif (now - silence_start_time) >= args.silence_timeout:
                        # ✅ ĐÃ IM LẶNG VƯỢT QUÁ silence_timeout (0.8s) -> DỨT CÂU NGAY!
                        current_state = STATE_WAIT_WAKE
                        audio_to_transcribe = list(speech_buffer)
                        speech_buffer.clear()
                        is_speaking = False
                        silence_start_time = None
                        speech_start_time = None

                        time_str = datetime.now().strftime("%H:%M:%S")
                        print(f"\n   ✂️ [{time_str}] [NGẮT CÂU THÀNH CÔNG] Đã phát hiện {args.silence_timeout:.2f}s im lặng sau câu nói.")

                        import threading
                        threading.Thread(
                            target=process_stt,
                            args=(audio_to_transcribe, session_count, last_score),
                            daemon=True
                        ).start()
                        return

                # Giới hạn an toàn: tự động dứt câu nếu người dùng nói quá dài (max_duration)
                if speech_dur >= args.max_duration:
                    current_state = STATE_WAIT_WAKE
                    audio_to_transcribe = list(speech_buffer)
                    speech_buffer.clear()
                    is_speaking = False
                    silence_start_time = None
                    speech_start_time = None

                    print(f"\n   ✂️ [NGẮT CÂU] Đạt giới hạn tối đa {args.max_duration:.1f}s.")
                    import threading
                    threading.Thread(
                        target=process_stt,
                        args=(audio_to_transcribe, session_count, last_score),
                        daemon=True
                    ).start()
                    return

            # Hết hạn 7.0s nếu người dùng hoàn toàn không nói gì sau khi gọi Hey Mirror
            if (now - listen_start_time) >= 7.0 and not is_speaking:
                print("\n   ⏱️ [HẾT GIỜ] Không nhận được câu lệnh nào sau khi gọi 'Hey Mirror'.")
                current_state = STATE_WAIT_WAKE
                speech_buffer.clear()
                is_speaking = False
                silence_start_time = None
                speech_start_time = None
                print("\n[✦ SẴN SÀNG] Đang chờ từ khóa 'Hey Mirror' tiếp theo...")

    def process_stt(chunks: List[np.ndarray], s_id: int, wake_score: float):
        if not chunks:
            return

        full_audio = np.concatenate(chunks, axis=0)
        dur = len(full_audio) / SAMPLE_RATE

        # Bỏ qua nếu quá ngắn (< 0.3s)
        if dur < 0.30:
            print(f"\n   ⚠️ Đoạn âm thanh quá ngắn ({dur:.2f}s), đã bỏ qua.")
            print("\n[✦ SẴN SÀNG] Đang chờ từ khóa 'Hey Mirror' tiếp theo...")
            return

        save_wav(wav_path, full_audio, SAMPLE_RATE)
        print(f"\n   ⏳ Đang giải mã {dur:.2f}s âm thanh qua Hybrid STT...")

        t0 = time.perf_counter()
        clean_text, latency = stt_engine.transcribe_samples(full_audio, SAMPLE_RATE)

        # Lọc các từ mồ côi của wakeword nếu còn sót
        wake_variants = ["hey mirror", "hay mirror", "ê mirror", "ê mi rơ", "mirror"]
        filtered_text = clean_text
        for v in wake_variants:
            if filtered_text.startswith(v):
                filtered_text = filtered_text[len(v):].strip()

        print("\n" + "="*70)
        print(f"🎉 HOÀN THÀNH LUỒNG (LƯỢT #{s_id})")
        print("="*70)
        print(f"  • Từ khóa đánh thức    : 'Hey Mirror' (Khớp {wake_score*100:.1f}%)")
        print(f"  • Thời lượng câu lệnh  : {dur:.2f} giây (lưu tại test/last_command.wav)")
        print(f"  • Thời gian giải mã STT: {latency:.3f} giây")
        if filtered_text:
            print(f"\n      👉 VĂN BẢN TIẾNG VIỆT NHẬN DẠNG: \"{filtered_text.upper()}\"")
        else:
            print(f"\n      ℹ️ (Không nhận diện được từ ngữ rõ ràng)")
        print("="*70)
        print("\n[✦ SẴN SÀNG] Đang chờ từ khóa 'Hey Mirror' tiếp theo...")

    stream = sd.InputStream(
        samplerate=SAMPLE_RATE,
        blocksize=CHUNK_SIZE,
        device=dev_idx,
        channels=1,
        dtype="float32",
        callback=audio_callback
    )

    with stream:
        print("[✦ SẴN SÀNG] Đang chờ bạn nói 'Hey Mirror'...")
        while True:
            vu_bar = render_bar(current_rms * 12.0, max_val=1.0, length=12)
            if current_state == STATE_WAIT_WAKE:
                sc_bar = render_bar(current_score, max_val=args.threshold, length=12)
                pct = min(100, int(current_score * 100))
                sys.stdout.write(f"\r🎙️ [CHỜ TỪ KHÓA] Mic: [{vu_bar}] | Score: [{sc_bar}] {pct:3d}% | Ồn phòng: {ambient_noise_level:.3f} ")
            elif current_state == STATE_LISTENING:
                if is_speaking:
                    if silence_start_time is not None:
                        silence_dur = time.time() - silence_start_time
                        silence_bar = render_bar(silence_dur, max_val=args.silence_timeout, length=10)
                        sys.stdout.write(f"\r🎙️ [⏳ LẶNG {silence_dur:3.1f}s/{args.silence_timeout:.1f}s: {silence_bar}] Mic: [{vu_bar}] Đang đợi dứt câu...   ")
                    else:
                        sys.stdout.write(f"\r🎙️ [🗣️ ĐANG NÓI CÂU LỆNH] Mic: [{vu_bar}] RMS: {current_rms:.3f} > {current_dynamic_thresh:.3f}         ")
                else:
                    sys.stdout.write(f"\r🎙️ [👂 ĐANG LẮNG NGHE] Mic: [{vu_bar}] Chờ bạn cất tiếng... (Ngưỡng: {current_dynamic_thresh:.3f}) ")
            sys.stdout.flush()
            time.sleep(0.04)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n🛑 Đã dừng chương trình kiểm thử.")


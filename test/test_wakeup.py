"""
====================================================================
      TEST WAKEUP: KIỂM THỬ NHẬN DIỆN TỪ KHÓA 'HEY MIRROR'
                  (SỬ DỤNG OPENWAKEWORD ONNX)
====================================================================
Cách sử dụng:
1. Chạy chương trình: .MMenv/bin/python3 test/test_wakeup.py
2. Nói rõ ràng "Hey Mirror" trước Micro.
3. Quan sát:
   - Thanh VU Meter đo âm lượng Micro.
   - Thanh Confidence Bar thể hiện độ khớp phần trăm của từ khóa.
4. Khi vượt ngưỡng kích hoạt:
   - Hệ thống hiển thị biểu tượng [ĐÁNH THỨC THÀNH CÔNG].
   - Lưu 1.5 giây âm thanh từ khóa vào test/last_wakeword.wav để nghe lại.
5. Nhấn [Ctrl+C] để THOÁT.
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


def render_bar(val: float, max_val: float = 1.0, length: int = 16) -> str:
    """Vẽ thanh tiến trình đồ họa"""
    ratio = min(1.0, max(0.0, val / max_val))
    filled = int(round(length * ratio))
    return "█" * filled + "░" * (length - filled)


def save_wav(filepath: str, audio_data: np.ndarray, sample_rate: int = 16000):
    """Lưu mảng audio float32 sang file WAV"""
    int16_data = (np.clip(audio_data, -1.0, 1.0) * 32767.0).astype(np.int16)
    with wave.open(filepath, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(int16_data.tobytes())


def main():
    default_thresh = float(os.getenv("WAKEWORD_THRESHOLD", "0.65"))
    default_gain = float(os.getenv("MIC_SOFTWARE_GAIN", "2.2"))

    parser = argparse.ArgumentParser(description="Kiểm thử nhận diện từ khóa 'Hey Mirror' qua openWakeWord")
    parser.add_argument("--device", type=int, default=None, help="Chỉ số index của micro")
    parser.add_argument("--threshold", type=float, default=default_thresh, help=f"Ngưỡng kích hoạt [0.1 - 1.0] (mặc định {default_thresh:.2f})")
    parser.add_argument("--gain", type=float, default=default_gain, help=f"Hệ số khuếch đại tiền xử lý mic (mặc định {default_gain:.1f}x)")
    parser.add_argument("--cooldown", type=float, default=1.8, help="Thời gian chờ chống kích hoạt lặp lại (giây, mặc định 1.8)")
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

    # Khởi tạo bộ nhận diện openWakeWord
    print("⏳ Đang nạp mô hình openWakeWord (Hey Mirror)...")
    ww_detector = get_wakeword_detector()
    if not ww_detector or not ww_detector.is_ready:
        print("[❌ LỖI] Không thể nạp mô hình openWakeWord từ models/wakeword/hey_mirror.onnx")
        return

    ww_detector.threshold = args.threshold
    ww_detector.reset()

    SAMPLE_RATE = 16000
    CHUNK_SIZE = 1280
    test_dir = os.path.join(PROJECT_ROOT, "test")
    os.makedirs(test_dir, exist_ok=True)
    wav_save_path = os.path.join(test_dir, "last_wakeword.wav")

    print(f"""
╔══════════════════════════════════════════════════════════════════════╗
║             🔥 TEST WAKEUP — TỪ KHÓA 'HEY MIRROR'                    ║
╠══════════════════════════════════════════════════════════════════════╣
║ • Microphone đang dùng : [{dev_idx}] {dev_name:<39}║
║ • Ngưỡng kích hoạt     : {args.threshold*100:5.1f}% (Độ khớp tối thiểu)              ║
║ • Tiền khuếch đại Gain : {args.gain:5.1f}x (Software Pre-amp)                 ║
║ • Thời gian Cooldown   : {args.cooldown:5.1f}s chống kích hoạt kép                   ║
║ • Mô hình sử dụng      : openWakeWord (hey_mirror.onnx)              ║
╠══════════════════════════════════════════════════════════════════════╣
║  👉 Hãy nói "Hey Mirror" trước mic để kiểm tra độ nhạy               ║
║  👉 Nhấn [Ctrl+C] để kết thúc                                        ║
╚══════════════════════════════════════════════════════════════════════╝
""")

    # Bộ đệm lưu ~1.5 giây âm thanh trước lúc kích hoạt
    buffer_len = int(SAMPLE_RATE * 1.5 // CHUNK_SIZE)
    history_buffer = deque(maxlen=buffer_len)

    current_rms = 0.0
    current_score = 0.0
    last_trigger_time = 0.0
    trigger_count = 0

    def audio_callback(indata, frames, time_info, status):
        nonlocal current_rms, current_score, last_trigger_time, trigger_count

        chunk = indata[:, 0].copy()
        if args.gain != 1.0:
            chunk = np.clip(chunk * args.gain, -1.0, 1.0)

        rms = float(np.sqrt(np.mean(chunk**2)))
        current_rms = rms
        history_buffer.append(chunk)

        # Xử lý nhận diện qua openWakeWord
        detected, score = ww_detector.process_chunk(chunk)
        current_score = float(score)

        now = time.time()
        if detected and (now - last_trigger_time >= args.cooldown):
            last_trigger_time = now
            trigger_count += 1

            # Lưu file âm thanh vừa bắt được
            if history_buffer:
                full_snippet = np.concatenate(list(history_buffer), axis=0)
                save_wav(wav_save_path, full_snippet, SAMPLE_RATE)

            time_str = datetime.now().strftime("%H:%M:%S")
            sys.stdout.write(
                f"\n\n🔥 [{time_str}] [ĐÁNH THỨC THÀNH CÔNG #{trigger_count}] 'Hey Mirror' "
                f"(Khớp: {score*100:5.1f}% | Ngưỡng: {args.threshold*100:.1f}%)\n"
                f"   💾 Âm thanh từ khóa đã lưu vào: test/last_wakeword.wav\n"
            )
            sys.stdout.flush()

    stream = sd.InputStream(
        samplerate=SAMPLE_RATE,
        blocksize=CHUNK_SIZE,
        device=dev_idx,
        channels=1,
        dtype="float32",
        callback=audio_callback
    )

    with stream:
        print("[✦ SẴN SÀNG] Đang lắng nghe từ khóa 'Hey Mirror'...")
        while True:
            # Hiển thị trạng thái thời gian thực
            now = time.time()
            in_cooldown = (now - last_trigger_time < args.cooldown)
            cd_text = f"⏳ Cooldown {args.cooldown - (now - last_trigger_time):3.1f}s" if in_cooldown else "🟢 Sẵn sàng  "

            vu_bar = render_bar(current_rms * 12.0, max_val=1.0, length=12)
            score_bar = render_bar(current_score, max_val=args.threshold, length=14)
            pct = min(100, int(current_score * 100))

            sys.stdout.write(
                f"\r🎙️ Mic: [{vu_bar}] | Score: [{score_bar}] {pct:3d}% | {cd_text} | Kích hoạt: #{trigger_count}"
            )
            sys.stdout.flush()
            time.sleep(0.04)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n🛑 Đã dừng kiểm thử từ khóa đánh thức.")


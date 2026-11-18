"""
====================================================================
        TEST RECORD: KIỂM THỬ THU ÂM MICROPHONE BẰNG PHÍM [SPACE]
====================================================================
Cách sử dụng:
1. Nhấn phím [SPACE] để BẮT ĐẦU THU ÂM.
2. Nói bất kỳ câu nào vào Micro (quan sát thanh VU Meter đo âm lượng).
3. Nhấn phím [SPACE] lần nữa để DỪNG THU ÂM.
4. Hệ thống sẽ:
   - Áp dụng hệ số tiền khuếch đại (Software Pre-amp Gain).
   - Đo lường cường độ âm thanh (RMS, Peak, Dynamic Range).
   - Đánh giá chất lượng tín hiệu (quá nhỏ / tốt / vỡ tiếng).
   - Lưu tệp âm thanh vào: test/recorded_test.wav.
5. Nhấn phím [q] để THOÁT.
====================================================================
"""

import argparse
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

try:
    import sounddevice as sd
    HAS_SOUNDDEVICE = True
except ImportError:
    sd = None
    HAS_SOUNDDEVICE = False


class InstantKeyReader:
    """Lớp bắt phím tức thì không cần nhấn Enter (hỗ trợ Linux & Windows)"""
    def __init__(self):
        self.old_settings = None

    def __enter__(self):
        if os.name != "nt" and sys.stdin.isatty():
            try:
                import termios
                import tty
                self.old_settings = termios.tcgetattr(sys.stdin)
                tty.setcbreak(sys.stdin.fileno())
            except Exception:
                pass
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if os.name != "nt" and sys.stdin.isatty() and self.old_settings is not None:
            try:
                import termios
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.old_settings)
            except Exception:
                pass

    def read_key(self) -> Optional[str]:
        if os.name == "nt":
            import msvcrt
            if msvcrt.kbhit():
                try:
                    return msvcrt.getch().decode("utf-8", errors="ignore")
                except Exception:
                    return ""
            return None
        else:
            if not sys.stdin.isatty():
                return None
            import select
            r, _, _ = select.select([sys.stdin], [], [], 0.03)
            if r:
                return sys.stdin.read(1)
            return None


def get_available_input_devices() -> List[Tuple[int, str, int]]:
    """Lấy danh sách tất cả các micro có kênh thu âm"""
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
    """Tự động chọn micro tối ưu (USB / ALSA / PipeWire)"""
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


def render_vu_meter(rms: float, length: int = 16) -> str:
    """Tạo thanh đo cường độ âm thanh VU Meter trực quan"""
    norm = min(1.0, max(0.0, float(rms) * 15.0))
    filled = int(round(length * norm))
    return "█" * filled + "░" * (length - filled)


def save_wav(filepath: str, audio_data: np.ndarray, sample_rate: int = 16000):
    """Lưu mảng audio float32 sang file WAV 16-bit PCM"""
    int16_data = (np.clip(audio_data, -1.0, 1.0) * 32767.0).astype(np.int16)
    with wave.open(filepath, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(int16_data.tobytes())


def main():
    default_gain = float(os.getenv("MIC_SOFTWARE_GAIN", "2.2"))

    parser = argparse.ArgumentParser(description="Kiểm thử thu âm Microphone bằng phím Space")
    parser.add_argument("--device", type=int, default=None, help="Chỉ số index của micro (tự động chọn nếu bỏ trống)")
    parser.add_argument("--gain", type=float, default=default_gain, help=f"Hệ số khuếch đại tiền xử lý mic (mặc định {default_gain:.1f}x)")
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

    SAMPLE_RATE = 16000
    CHUNK_SIZE = 1280
    test_dir = os.path.join(PROJECT_ROOT, "test", "records")
    os.makedirs(test_dir, exist_ok=True)
    wav_path = os.path.join(test_dir, "recorded_test.wav")

    print(f"""
╔══════════════════════════════════════════════════════════════════════╗
║               🎙️ TEST RECORD — KIỂM THỬ THU ÂM MICRO                 ║
╠══════════════════════════════════════════════════════════════════════╣
║ • Microphone đang dùng : [{dev_idx}] {dev_name:<39}║
║ • Tiền khuếch đại Gain : {args.gain:.1f}x (Software Pre-amp)                 ║
║ • Tần số lấy mẫu       : 16000 Hz (Mono PCM 16-bit)                  ║
║ • Thư mục lưu bản thu  : test/records/recorded_test.wav              ║
╠══════════════════════════════════════════════════════════════════════╣
║  👉 Nhấn phím [SPACE] một lần : BẮT ĐẦU THU ÂM                       ║
║  👉 Nhấn phím [SPACE] lần nữa : DỪNG THU & XEM PHÂN TÍCH ÂM LƯỢNG    ║
║  👉 Nhấn phím [q]             : THOÁT                                ║
╚══════════════════════════════════════════════════════════════════════╝
""")

    is_recording = False
    recorded_chunks = []
    current_rms = 0.0
    current_peak = 0.0
    record_start_time = 0.0
    record_count = 0

    def audio_callback(indata, frames, time_info, status):
        nonlocal current_rms, current_peak
        chunk = indata[:, 0].copy()
        if args.gain != 1.0:
            chunk = np.clip(chunk * args.gain, -1.0, 1.0)

        rms = float(np.sqrt(np.mean(chunk**2)))
        peak = float(np.max(np.abs(chunk)))
        current_rms = rms
        current_peak = peak

        if is_recording:
            recorded_chunks.append(chunk)

    stream = sd.InputStream(
        samplerate=SAMPLE_RATE,
        blocksize=CHUNK_SIZE,
        device=dev_idx,
        channels=1,
        dtype="float32",
        callback=audio_callback
    )

    with stream, InstantKeyReader() as key_reader:
        print("[✦ SẴN SÀNG] Nhấn phím [SPACE] để bắt đầu thu âm...")
        while True:
            key = key_reader.read_key()
            if key:
                if key.lower() == "q":
                    print("\n👋 Đã thoát chương trình kiểm thử.")
                    break
                elif key == " ":
                    if not is_recording:
                        # Bắt đầu thu
                        is_recording = True
                        recorded_chunks = []
                        record_start_time = time.time()
                        record_count += 1
                        print(f"\n🔴 [ĐANG THU ÂM #{record_count}] Nói vào Micro ngay bây giờ...")
                    else:
                        # Dừng thu
                        is_recording = False
                        total_dur = time.time() - record_start_time
                        if not recorded_chunks:
                            print("\n⚠️ Không có dữ liệu âm thanh được ghi lại.")
                            continue

                        audio_data = np.concatenate(recorded_chunks, axis=0)
                        save_wav(wav_path, audio_data, SAMPLE_RATE)

                        # Phân tích âm lượng
                        rms_total = float(np.sqrt(np.mean(audio_data**2)))
                        peak_total = float(np.max(np.abs(audio_data)))
                        rms_db = 20 * np.log10(max(rms_total, 1e-5))
                        peak_db = 20 * np.log10(max(peak_total, 1e-5))

                        # Đánh giá chất lượng tín hiệu
                        if peak_total > 0.98:
                            quality = "⚠️ VỠ TIẾNG (Clipping) - Nên giảm --gain"
                        elif rms_total < 0.008:
                            quality = "❌ QUÁ NHỎ (Khó nhận diện) - Nên nói to hơn hoặc tăng --gain"
                        elif rms_total < 0.025:
                            quality = "🟡 HƠI NHỎ - Đạt mức tối thiểu, Peak Normalization sẽ hỗ trợ"
                        elif rms_total <= 0.35:
                            quality = "🟢 TỐT / RẤT CHUẨN (Tín hiệu đẹp cho ASR)"
                        else:
                            quality = "🟡 KHÁ LỚN"

                        print("\n" + "="*70)
                        print(f"📊 KẾT QUẢ THU ÂM (LƯỢT #{record_count}) - {datetime.now().strftime('%H:%M:%S')}")
                        print("="*70)
                        print(f"  • Thời lượng thu âm   : {total_dur:.2f} giây ({len(audio_data)} mẫu)")
                        print(f"  • Âm lượng RMS        : {rms_total:.4f} ({rms_db:.1f} dBFS)")
                        print(f"  • Âm lượng Đỉnh (Peak): {peak_total:.4f} ({peak_db:.1f} dBFS)")
                        print(f"  • Đánh giá chất lượng : {quality}")
                        print(f"  • Tệp âm thanh đã lưu : test/records/recorded_test.wav")
                        print("="*70)
                        print("\n[✦ SẴN SÀNG] Nhấn [SPACE] để thu âm lượt tiếp theo (hoặc 'q' để thoát)...")

            # Cập nhật thanh hiển thị khi đang thu âm
            if is_recording:
                elapsed = time.time() - record_start_time
                vu_bar = render_vu_meter(current_rms, length=16)
                vol_pct = min(100, int(current_rms * 1500))
                sys.stdout.write(
                    f"\r🎙️ VU: [{vu_bar}] {vol_pct:3d}% | Đỉnh: {current_peak:.2f} | ⏱️ {elapsed:4.1f}s | Nhấn [SPACE] để dừng..."
                )
                sys.stdout.flush()

            time.sleep(0.03)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n🛑 Đã dừng chương trình kiểm thử.")


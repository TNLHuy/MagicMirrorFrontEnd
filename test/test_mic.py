"""
====================================================================
        TEST MIC: BỘ ĐO LƯỜNG, CHẨN ĐOÁN & THU ÂM MICROPHONE
====================================================================
Chức năng:
1. Quét phần cứng và kiểm tra chi tiết thiết bị Microphone (ALSA / PipeWire).
2. Đo kiểm cường độ âm lượng (RMS, Peak dBFS) và đo mức ồn phòng (Noise Floor).
3. Thu âm bằng 2 chế độ:
   - Nhấn phím [SPACE] để bắt đầu & dừng tự do.
   - Hoặc thu âm cố định số giây qua tham số: --seconds 5
4. Tự động lưu tất cả các bản ghi vào thư mục:
   test/records/mic_YYYYMMDD_HHMMSS.wav (kèm tệp test/records/latest.wav)
5. Nghe lại âm thanh vừa thu trực tiếp qua loa (--play).
6. Phân tích chi tiết tỷ số tín hiệu trên nhiễu (SNR) và chất lượng mic.
====================================================================
"""

import argparse
from datetime import datetime
import os
import sys
import time
import wave
from typing import Optional, List, Tuple, Dict, Any
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


# Thư mục lưu trữ các bản ghi âm
RECORDS_DIR = os.path.join(PROJECT_ROOT, "test", "records")
os.makedirs(RECORDS_DIR, exist_ok=True)


class InstantKeyReader:
    """Lớp bắt phím Space tức thì không cần nhấn Enter (Linux & Windows)"""
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
    """Tìm tất cả các thiết bị micro có thể thu âm"""
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
    """Tự động chọn micro USB / PipeWire tốt nhất"""
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


def save_audio_file(audio_data: np.ndarray, sample_rate: int = 16000) -> Tuple[str, str]:
    """Lưu file âm thanh vào test/records/ với timestamp và bản latest.wav"""
    int16_data = (np.clip(audio_data, -1.0, 1.0) * 32767.0).astype(np.int16)

    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"mic_{timestamp_str}.wav"
    filepath = os.path.join(RECORDS_DIR, filename)
    latest_path = os.path.join(RECORDS_DIR, "latest.wav")

    # Lưu file có timestamp
    with wave.open(filepath, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(int16_data.tobytes())

    # Lưu file latest.wav
    with wave.open(latest_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(int16_data.tobytes())

    return filepath, latest_path


def play_audio(audio_data: np.ndarray, sample_rate: int = 16000):
    """Phát lại âm thanh vừa thu qua loa để nghe thử"""
    if not HAS_SOUNDDEVICE:
        return
    try:
        print("\n🔊 Đang phát lại âm thanh qua loa...")
        sd.play(audio_data, samplerate=sample_rate)
        sd.wait()
        print("✅ Phát lại hoàn tất.")
    except Exception as e:
        print(f"⚠️ Không thể phát lại âm thanh: {e}")


def analyze_audio_quality(audio_data: np.ndarray, ambient_noise: float = 0.005) -> Dict[str, Any]:
    """Phân tích chuyên sâu chất lượng âm thanh"""
    rms = float(np.sqrt(np.mean(audio_data**2)))
    peak = float(np.max(np.abs(audio_data)))
    rms_db = 20 * np.log10(max(rms, 1e-5))
    peak_db = 20 * np.log10(max(peak, 1e-5))

    # Tỷ số tín hiệu trên nhiễu SNR (Signal-to-Noise Ratio)
    snr_db = 20 * np.log10(max(rms / max(ambient_noise, 1e-5), 1.0))

    if peak > 0.98:
        quality = "⚠️ VỠ TIẾNG (Clipping) — Tín hiệu bị quá tải biên độ, nên giảm --gain"
    elif rms < 0.008:
        quality = "❌ QUÁ NHỎ — Rất khó nhận diện ASR, cần nói gần mic hoặc tăng --gain"
    elif rms < 0.025:
        quality = "🟡 HƠI NHỎ — Đạt mức cơ bản, thuật toán Peak Normalization sẽ hỗ trợ bù đắp"
    elif rms <= 0.35:
        quality = "🟢 RẤT ĐẸP & CHUẨN — Tín hiệu lý tưởng cho nhận dạng giọng nói tiếng Việt"
    else:
        quality = "🟡 KHÁ LỚN — Âm lượng rất mạnh"

    return {
        "rms": rms,
        "peak": peak,
        "rms_db": rms_db,
        "peak_db": peak_db,
        "snr_db": snr_db,
        "quality": quality
    }


def list_records_folder():
    """In danh sách các bản ghi âm hiện có trong thư mục test/records/"""
    if not os.path.exists(RECORDS_DIR):
        return
    files = sorted([f for f in os.listdir(RECORDS_DIR) if f.endswith(".wav") and f != "latest.wav"])
    if not files:
        print("  (Chưa có bản ghi âm nào)")
        return

    print(f"\n📂 DANH SÁCH BẢN THU TRONG test/records/ (Tổng cộng: {len(files)} tệp):")
    for f in files[-8:]:  # Hiển thị tối đa 8 file gần nhất
        fp = os.path.join(RECORDS_DIR, f)
        size_kb = os.path.getsize(fp) / 1024.0
        mtime = datetime.fromtimestamp(os.path.getmtime(fp)).strftime("%H:%M:%S %d/%m")
        print(f"  • {f:<26} ({size_kb:5.1f} KB | {mtime})")


def main():
    default_gain = float(os.getenv("MIC_SOFTWARE_GAIN", "2.2"))

    parser = argparse.ArgumentParser(description="Kiểm thử và chẩn đoán Microphone — Lưu vào test/records/")
    parser.add_argument("--device", type=int, default=None, help="Chỉ số index của micro (tự động chọn nếu bỏ trống)")
    parser.add_argument("--gain", type=float, default=default_gain, help=f"Hệ số tiền khuếch đại mic (mặc định {default_gain:.1f}x)")
    parser.add_argument("--seconds", "-s", type=float, default=None, help="Thu âm cố định trong N giây (bỏ trống để dùng phím Space)")
    parser.add_argument("--play", "-p", action="store_true", help="Tự động phát lại qua loa sau khi thu xong")
    parser.add_argument("--list-devices", action="store_true", help="Xem danh sách thiết bị micro rồi thoát")
    parser.add_argument("--list-records", action="store_true", help="Xem danh sách các file thu âm đã lưu rồi thoát")
    args = parser.parse_args()

    if not HAS_SOUNDDEVICE:
        print("[❌ LỖI] Chưa cài đặt sounddevice. Hãy chạy: pip install sounddevice")
        return

    if args.list_records:
        list_records_folder()
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

    print(f"""
╔══════════════════════════════════════════════════════════════════════╗
║               🎙️ TEST MIC — ĐO LƯỜNG & THU ÂM MICRO                  ║
╠══════════════════════════════════════════════════════════════════════╣
║ • Microphone đang dùng : [{dev_idx}] {dev_name:<39}║
║ • Tiền khuếch đại Gain : {args.gain:.1f}x (Software Pre-amp)                 ║
║ • Tần số lấy mẫu       : 16000 Hz (Mono PCM 16-bit)                  ║
║ • Thư mục lưu bản thu  : test/records/                               ║
║ • Nghe lại qua loa     : {'🟢 BẬT (--play)' if args.play else '🟡 TẮT (thêm cờ --play để bật)':<43}║
╠══════════════════════════════════════════════════════════════════════╣
║  👉 Phím [SPACE] một lần : BẮT ĐẦU THU ÂM                            ║
║  👉 Phím [SPACE] lần nữa : DỪNG THU & LƯU VÀO FOLDER RECORDS         ║
║  👉 Phím [q]             : THOÁT                                     ║
╚══════════════════════════════════════════════════════════════════════╝
""")

    is_recording = False
    recorded_chunks = []
    current_rms = 0.0
    current_peak = 0.0
    ambient_noise_level = 0.005
    record_start_time = 0.0
    record_count = 0

    def audio_callback(indata, frames, time_info, status):
        nonlocal current_rms, current_peak, ambient_noise_level
        chunk = indata[:, 0].copy()
        if args.gain != 1.0:
            chunk = np.clip(chunk * args.gain, -1.0, 1.0)

        rms = float(np.sqrt(np.mean(chunk**2)))
        peak = float(np.max(np.abs(chunk)))
        current_rms = rms
        current_peak = peak

        # Đo mức ồn phòng khi không nói
        if not is_recording:
            ambient_noise_level = ambient_noise_level * 0.95 + rms * 0.05
        else:
            recorded_chunks.append(chunk)

    # -----------------------------------------------------------------
    # CHẾ ĐỘ 1: THU ÂM CỐ ĐỊNH THEO THỜI GIAN (--seconds)
    # -----------------------------------------------------------------
    if args.seconds is not None and args.seconds > 0:
        sec = args.seconds
        print(f"⏳ Đang thu âm cố định trong {sec:.1f} giây...")
        stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            blocksize=CHUNK_SIZE,
            device=dev_idx,
            channels=1,
            dtype="float32",
            callback=audio_callback
        )
        is_recording = True
        recorded_chunks = []
        with stream:
            t_end = time.time() + sec
            while time.time() < t_end:
                rem = max(0.0, t_end - time.time())
                vu_bar = render_vu_meter(current_rms, length=16)
                vol_pct = min(100, int(current_rms * 1500))
                sys.stdout.write(f"\r🎙️ VU: [{vu_bar}] {vol_pct:3d}% | Đỉnh: {current_peak:.2f} | Còn lại: {rem:4.1f}s...")
                sys.stdout.flush()
                time.sleep(0.03)

        audio_data = np.concatenate(recorded_chunks, axis=0) if recorded_chunks else np.zeros(160, dtype=np.float32)
        filepath, latest_path = save_audio_file(audio_data, SAMPLE_RATE)
        stats = analyze_audio_quality(audio_data, ambient_noise_level)

        print("\n\n" + "=" * 70)
        print(f"📊 KẾT QUẢ THU ÂM CỐ ĐỊNH ({sec:.1f}s)")
        print("=" * 70)
        print(f"  • Âm lượng RMS        : {stats['rms']:.4f} ({stats['rms_db']:.1f} dBFS)")
        print(f"  • Âm lượng Đỉnh (Peak): {stats['peak']:.4f} ({stats['peak_db']:.1f} dBFS)")
        print(f"  • Độ chênh lệch SNR   : {stats['snr_db']:.1f} dB (Tín hiệu / Nhiễu phòng)")
        print(f"  • Đánh giá chất lượng : {stats['quality']}")
        print(f"  • Bản ghi lưu tại     : {os.path.relpath(filepath, PROJECT_ROOT)}")
        print(f"  • Bản ghi latest      : {os.path.relpath(latest_path, PROJECT_ROOT)}")
        print("=" * 70)

        if args.play:
            play_audio(audio_data, SAMPLE_RATE)

        list_records_folder()
        return

    # -----------------------------------------------------------------
    # CHẾ ĐỘ 2: THU ÂM BẰNG PHÍM [SPACE] (INTERACTIVE)
    # -----------------------------------------------------------------
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
                    print("\n👋 Đã thoát kiểm thử Microphone.")
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
                            print("\n⚠️ Không có dữ liệu âm thanh.")
                            continue

                        audio_data = np.concatenate(recorded_chunks, axis=0)
                        filepath, latest_path = save_audio_file(audio_data, SAMPLE_RATE)
                        stats = analyze_audio_quality(audio_data, ambient_noise_level)

                        print("\n" + "=" * 70)
                        print(f"📊 KẾT QUẢ BẢN THU #{record_count} — {datetime.now().strftime('%H:%M:%S')}")
                        print("=" * 70)
                        print(f"  • Thời lượng thu âm   : {total_dur:.2f} giây ({len(audio_data)} mẫu)")
                        print(f"  • Âm lượng RMS        : {stats['rms']:.4f} ({stats['rms_db']:.1f} dBFS)")
                        print(f"  • Âm lượng Đỉnh (Peak): {stats['peak']:.4f} ({stats['peak_db']:.1f} dBFS)")
                        print(f"  • Tỷ số SNR / Ồn phòng: {stats['snr_db']:.1f} dB")
                        print(f"  • Đánh giá chất lượng : {stats['quality']}")
                        print(f"  • File lưu có ngày giờ: {os.path.relpath(filepath, PROJECT_ROOT)}")
                        print(f"  • File lưu bản mới nhất: {os.path.relpath(latest_path, PROJECT_ROOT)}")
                        print("=" * 70)

                        if args.play:
                            play_audio(audio_data, SAMPLE_RATE)

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

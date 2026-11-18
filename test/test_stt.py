"""
====================================================================
          TEST STT: KIỂM THỬ NHẬN DẠNG GIỌNG NÓI TIẾNG VIỆT
====================================================================
Cách sử dụng:
1. Kiểm thử tệp WAV có sẵn:
   .MMenv/bin/python3 test/test_stt.py --file test/last_command.wav
2. Thu âm trực tiếp bằng phím [SPACE] để kiểm tra câu nói:
   .MMenv/bin/python3 test/test_stt.py
3. So sánh trực tiếp Cloud STT vs Local Zipformer-30M trên cùng 1 đoạn âm thanh:
   .MMenv/bin/python3 test/test_stt.py --file test/last_command.wav --compare
====================================================================
"""

import argparse
import os
import sys
import time
import wave
from typing import Optional, Tuple
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

from backend.voice.stt_service import get_stt_engine, HybridSTT
from backend.voice.local_stt import get_local_stt

try:
    import sounddevice as sd
    HAS_SOUNDDEVICE = True
except ImportError:
    sd = None
    HAS_SOUNDDEVICE = False


class InstantKeyReader:
    """Lớp bắt phím tức thì không cần nhấn Enter"""
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


def read_wav_file(wav_path: str) -> Tuple[np.ndarray, int]:
    """Đọc file WAV và trả về mảng numpy float32 cùng tần số sample_rate"""
    with wave.open(wav_path, "rb") as wf:
        sr = wf.getframerate()
        n_frames = wf.getnframes()
        raw = wf.readframes(n_frames)
        samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    return samples, sr


def run_single_transcription(samples: np.ndarray, sample_rate: int, provider: str = "auto"):
    """Chạy phiên âm qua engine chỉ định"""
    engine = get_stt_engine(provider=provider)
    audio_dur = len(samples) / float(sample_rate)

    print(f"\n⏳ Đang gửi {audio_dur:.2f}s âm thanh vào STT Engine (Chế độ: '{provider.upper()}')...")
    t0 = time.perf_counter()
    text, latency = engine.transcribe_samples(samples, sample_rate)
    rtf = latency / max(audio_dur, 0.01)

    print("\n" + "="*70)
    print(f"🎯 KẾT QUẢ PHIÊN ÂM ({provider.upper()} STT)")
    print("="*70)
    print(f"  • Thời lượng file âm thanh : {audio_dur:.2f} giây")
    print(f"  • Thời gian xử lý          : {latency:.3f} giây (RTF: {rtf:.3f})")
    if text:
        print(f"\n      👉 VĂN BẢN TIẾNG VIỆT : \"{text.upper()}\"")
    else:
        print("\n      ⚠️ (Không nhận diện được từ ngữ rõ ràng)")
    print("="*70)


def run_comparison(samples: np.ndarray, sample_rate: int):
    """So sánh trực diện Cloud STT vs Local Zipformer-30M"""
    audio_dur = len(samples) / float(sample_rate)
    print(f"\n⚖️ SO SÁNH TRỰC DIỆN CLOUD STT VS LOCAL ZIPFORMER-30M ({audio_dur:.2f}s âm thanh)")
    print("-" * 75)

    # 1. Chạy Cloud STT (Google/Groq)
    cloud_engine = get_stt_engine(provider="auto")
    print("  [1/2] Đang chạy Cloud STT...")
    t0 = time.perf_counter()
    cloud_text, cloud_lat = cloud_engine.transcribe_samples(samples.copy(), sample_rate)

    # 2. Chạy Local Zipformer-30M
    local_engine = get_local_stt()
    print("  [2/2] Đang chạy Local Zipformer-30M...")
    t0 = time.perf_counter()
    local_text, local_lat = local_engine.transcribe_samples(samples.copy(), sample_rate)

    print("\n" + "="*75)
    print("📊 BẢNG SO SÁNH KẾT QUẢ ĐỘ CHÍNH XÁC & HIỆU NĂNG")
    print("="*75)
    print(f"{'Tiêu chí':<25} | {'Cloud STT (Kiểu Xiaozhi)':<25} | {'Local Zipformer-30M':<20}")
    print("-" * 75)
    print(f"{'Văn bản nhận diện':<25} | {cloud_text or '(Trống)':<25} | {local_text or '(Trống)':<20}")
    print(f"{'Thời gian xử lý':<25} | {cloud_lat:5.3f}s{'':<19} | {local_lat:5.3f}s{'':<14}")
    print(f"{'Tỷ lệ RTF':<25} | {cloud_lat/max(audio_dur,0.01):5.3f}{'':<20} | {local_lat/max(audio_dur,0.01):5.3f}{'':<15}")
    print("="*75)


def record_live_spacebar(device_index: Optional[int] = None, gain: float = 2.2) -> Tuple[np.ndarray, int]:
    """Thu âm trực tiếp bằng phím Space"""
    SAMPLE_RATE = 16000
    CHUNK_SIZE = 1280
    recorded_chunks = []
    is_recording = False
    current_rms = 0.0

    def audio_callback(indata, frames, time_info, status):
        nonlocal current_rms
        chunk = indata[:, 0].copy()
        if gain != 1.0:
            chunk = np.clip(chunk * gain, -1.0, 1.0)
        current_rms = float(np.sqrt(np.mean(chunk**2)))
        if is_recording:
            recorded_chunks.append(chunk)

    stream = sd.InputStream(
        samplerate=SAMPLE_RATE,
        blocksize=CHUNK_SIZE,
        device=device_index,
        channels=1,
        dtype="float32",
        callback=audio_callback
    )

    with stream, InstantKeyReader() as key_reader:
        print("""
╔══════════════════════════════════════════════════════════════════════╗
║               🎙️ THU ÂM BẰNG PHÍM [SPACE] ĐỂ TEST STT                ║
╠══════════════════════════════════════════════════════════════════════╣
║  👉 Nhấn [SPACE] : BẮT ĐẦU NÓI CÂU LỆNH                              ║
║  👉 Nhấn [SPACE] : DỪNG & GỬI VÀO BỘ GIẢI MÃ STT                     ║
║  👉 Nhấn [q]     : THOÁT                                             ║
╚══════════════════════════════════════════════════════════════════════╝
""")
        rec_start = 0.0
        while True:
            k = key_reader.read_key()
            if k:
                if k.lower() == "q":
                    sys.exit(0)
                elif k == " ":
                    if not is_recording:
                        is_recording = True
                        recorded_chunks = []
                        rec_start = time.time()
                        print("\n🔴 [ĐANG THU] Hãy nói một câu tiếng Việt bất kỳ...")
                    else:
                        is_recording = False
                        break

            if is_recording:
                elapsed = time.time() - rec_start
                vol_pct = min(100, int(current_rms * 1500))
                sys.stdout.write(f"\r🎙️ Đang thu âm: {elapsed:4.1f}s | Âm lượng: {vol_pct:3d}% | Nhấn [SPACE] để dừng...")
                sys.stdout.flush()
            time.sleep(0.03)

    if not recorded_chunks:
        print("\n⚠️ Không có âm thanh nào được ghi lại.")
        sys.exit(0)

    audio_data = np.concatenate(recorded_chunks, axis=0)
    # Lưu để tham khảo
    test_wav = os.path.join(PROJECT_ROOT, "test", "recorded_test.wav")
    int16_data = (np.clip(audio_data, -1.0, 1.0) * 32767.0).astype(np.int16)
    with wave.open(test_wav, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(int16_data.tobytes())

    return audio_data, SAMPLE_RATE


def main():
    parser = argparse.ArgumentParser(description="Kiểm thử nhận dạng giọng nói STT tiếng Việt")
    parser.add_argument("--file", type=str, default=None, help="Đường dẫn file WAV cần kiểm thử")
    parser.add_argument("--provider", type=str, default="auto", choices=["auto", "google", "groq", "gemini", "local"],
                        help="Engine STT: auto (khuyên dùng), google, groq, gemini, local (Zipformer-30M)")
    parser.add_argument("--compare", action="store_true", help="Chạy so sánh trực diện Cloud STT vs Local Zipformer-30M")
    parser.add_argument("--gain", type=float, default=2.2, help="Hệ số khuếch đại khi thu âm live bằng Space (mặc định 2.2x)")
    args = parser.parse_args()

    # Xác định dữ liệu âm thanh
    if args.file:
        if not os.path.exists(args.file):
            print(f"[❌ LỖI] Không tìm thấy file âm thanh tại: {args.file}")
            return
        print(f"📂 Đang nạp tệp âm thanh: {args.file}")
        samples, sr = read_wav_file(args.file)
    else:
        # Nếu có file test có sẵn thì gợi ý, nếu không thì thu âm bằng phím Space
        fallback_wav = os.path.join(PROJECT_ROOT, "test", "last_command.wav")
        if not HAS_SOUNDDEVICE and os.path.exists(fallback_wav):
            print(f"📂 Sử dụng file âm thanh có sẵn: {fallback_wav}")
            samples, sr = read_wav_file(fallback_wav)
        else:
            samples, sr = record_live_spacebar(gain=args.gain)

    # Chạy kiểm thử hoặc so sánh
    if args.compare:
        run_comparison(samples, sr)
    else:
        run_single_transcription(samples, sr, provider=args.provider)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n🛑 Đã dừng kiểm thử STT.")


"""
====================================================================
        TEST SPEAKER: BỘ ĐO LƯỜNG, KIỂM TRA & PHÁT ÂM THANH LOA
====================================================================
Chức năng:
1. Tự động quét phần cứng loa / ngõ ra âm thanh (HDMI, USB Audio, 3.5mm, ALSA).
2. Phát âm kiểm tra nhanh (Chime / Melody / Beep).
3. Kiểm tra cân bằng 2 kênh Loa Trái (Left) & Loa Phải (Right).
4. Phát file âm thanh WAV tùy chọn hoặc bản ghi mic mới nhất (latest.wav).
5. Hỗ trợ tự động chuyển đổi định dạng qua ALSA plughw (tương thích 100% Raspberry Pi 5).
====================================================================
"""

import argparse
import math
import os
import struct
import subprocess
import sys
import time
import wave
from typing import List, Dict, Optional, Tuple
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

RECORDS_DIR = os.path.join(PROJECT_ROOT, "test", "records")
TEMP_WAV = "/tmp/mm_speaker_test.wav"


def get_alsa_playback_cards() -> List[Dict[str, any]]:
    """Lấy danh sách các card âm thanh ngõ ra từ ALSA (aplay -l)"""
    devices = []
    try:
        res = subprocess.run(["aplay", "-l"], capture_output=True, text=True, check=True)
        lines = res.stdout.splitlines()
        for line in lines:
            if line.startswith("card "):
                # card 1: vc4hdmi1 [vc4-hdmi-1], device 0: MAI PCM i2s-hifi-0 [MAI PCM i2s-hifi-0]
                try:
                    parts = line.split(":")
                    card_num = int(parts[0].replace("card", "").strip())
                    rest = parts[1].strip()
                    card_name = rest.split("[")[0].strip()
                    
                    dev_num = 0
                    if "device " in line:
                        dev_part = line.split("device ")[1].split(":")[0]
                        dev_num = int(dev_part.strip())

                    devices.append({
                        "card": card_num,
                        "device": dev_num,
                        "name": card_name,
                        "raw": line.strip()
                    })
                except Exception:
                    pass
    except Exception:
        pass
    return devices


def select_best_playback_device(preferred_card: Optional[int] = None) -> Tuple[int, int, str]:
    """Tự động chọn ngõ ra loa tốt nhất (USB Audio hoặc HDMI)"""
    cards = get_alsa_playback_cards()
    if not cards:
        return (0, 0, "default")

    if preferred_card is not None:
        for c in cards:
            if c["card"] == preferred_card:
                return (c["card"], c["device"], c["name"])

    # Ưu tiên USB loa ngoài hoặc DAC cắm thêm
    for c in cards:
        name_lower = c["name"].lower()
        if any(k in name_lower for k in ["usb", "speaker", "dac", "headset"]):
            return (c["card"], c["device"], c["name"])

    # Ưu tiên card 1 (thường là cổng HDMI chính có cắm màn hình trên Pi 5)
    for c in cards:
        if c["card"] == 1:
            return (c["card"], c["device"], c["name"])

    first = cards[0]
    return (first["card"], first["device"], first["name"])


def generate_chime_wav(filename: str, sample_rate: int = 44100, volume: float = 0.5):
    """Tạo file âm thanh chuông báo 3 nốt Đô - Mi - Sol (C5 - E5 - G5) rất êm tai"""
    notes = [523.25, 659.25, 783.99]  # C5, E5, G5
    durations = [0.18, 0.18, 0.45]
    total_samples = []

    for freq, dur in zip(notes, durations):
        n_samples = int(sample_rate * dur)
        t = np.linspace(0, dur, n_samples, endpoint=False)
        # Envelope tạo tiếng chuông ngân mượt
        decay = np.exp(-t * 5.0)
        signal = np.sin(2 * np.pi * freq * t) * decay * volume
        # Thêm chút họa âm nhẹ
        signal += np.sin(2 * np.pi * (freq * 2) * t) * decay * 0.3 * volume
        total_samples.append(signal)

    audio = np.concatenate(total_samples)
    int16_audio = (np.clip(audio, -1.0, 1.0) * 32767.0).astype(np.int16)
    stereo = np.column_stack((int16_audio, int16_audio))

    with wave.open(filename, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(stereo.tobytes())


def generate_channel_test_wav(filename: str, sample_rate: int = 44100, volume: float = 0.5):
    """Tạo âm thanh kiểm tra từng kênh: Trái -> Phải -> Cả hai"""
    dur = 0.6
    n_samples = int(sample_rate * dur)
    silence = np.zeros(int(sample_rate * 0.25), dtype=np.int16)

    def tone(freq):
        t = np.linspace(0, dur, n_samples, endpoint=False)
        decay = np.exp(-t * 2.0)
        return (np.sin(2 * np.pi * freq * t) * decay * volume * 32767.0).astype(np.int16)

    left_tone = tone(440.0)    # Nốt La (Kênh trái)
    right_tone = tone(554.37)  # Nốt Đô thăng (Kênh phải)
    both_tone = tone(659.25)   # Nốt Mi (Cả 2 kênh)

    # 1. Kênh trái kêu
    p1_l = left_tone
    p1_r = np.zeros_like(left_tone)

    # 2. Nghỉ
    p2_l = silence
    p2_r = silence

    # 3. Kênh phải kêu
    p3_l = np.zeros_like(right_tone)
    p3_r = right_tone

    # 4. Nghỉ
    p4_l = silence
    p4_r = silence

    # 5. Cả hai kênh cùng kêu
    p5_l = both_tone
    p5_r = both_tone

    all_l = np.concatenate([p1_l, p2_l, p3_l, p4_l, p5_l])
    all_r = np.concatenate([p1_r, p2_r, p3_r, p4_r, p5_r])
    stereo = np.column_stack((all_l, all_r))

    with wave.open(filename, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(stereo.tobytes())


def play_wav_file(filepath: str, card: int = 1, dev: int = 0) -> bool:
    """Phát file WAV bằng sounddevice hoặc tự động fallback sang ALSA plughw"""
    if not os.path.exists(filepath):
        print(f"[❌ LỖI] Không tìm thấy file âm thanh: {filepath}")
        return False

    print(f"🔊 Đang phát: {os.path.basename(filepath)}...")

    # Cách 1: Ưu tiên dùng aplay plughw trên Linux (chuẩn nhất cho Raspberry Pi HDMI/USB)
    device_str = f"plughw:{card},{dev}"
    try:
        res = subprocess.run(["aplay", "-D", device_str, filepath], capture_output=True, text=True)
        if res.returncode == 0:
            print(f"✅ Phát thành công qua ngõ ra ALSA [{device_str}]")
            return True
        else:
            # Thử với device default
            res_def = subprocess.run(["aplay", "-D", "default", filepath], capture_output=True, text=True)
            if res_def.returncode == 0:
                print("✅ Phát thành công qua ALSA [default]")
                return True
    except Exception:
        pass

    # Cách 2: Dùng sounddevice
    if HAS_SOUNDDEVICE:
        try:
            with wave.open(filepath, "rb") as wf:
                sample_rate = wf.getframerate()
                n_channels = wf.getnchannels()
                frames = wf.readframes(wf.getnframes())
                audio_data = np.frombuffer(frames, dtype=np.int16)
                if n_channels > 1:
                    audio_data = audio_data.reshape(-1, n_channels)
                sd.play(audio_data, samplerate=sample_rate)
                sd.wait()
                print("✅ Phát thành công qua sounddevice.")
                return True
        except Exception as e:
            print(f"⚠️ sounddevice gặp lỗi: {e}")

    print("[❌ LỖI] Không thể phát âm thanh tới loa. Vui lòng kiểm tra cáp HDMI / Loa USB.")
    return False


def main():
    parser = argparse.ArgumentParser(description="Kiểm thử và chẩn đoán Loa / Ngõ ra âm thanh")
    parser.add_argument("--card", "-c", type=int, default=None, help="Chỉ định số ALSA card (ví dụ: 0, 1, 2)")
    parser.add_argument("--device", "-d", type=int, default=0, help="Chỉ định sub-device (mặc định 0)")
    parser.add_argument("--file", "-f", type=str, default=None, help="Đường dẫn file WAV cần phát thử")
    parser.add_argument("--latest", action="store_true", help="Phát bản ghi âm mic mới nhất (test/records/latest.wav)")
    parser.add_argument("--stereo", action="store_true", help="Kiểm tra phân kênh Loa Trái (Left) và Loa Phải (Right)")
    parser.add_argument("--volume", "-v", type=float, default=0.7, help="Âm lượng phát kiểm tra (0.1 đến 1.0, mặc định 0.7)")
    parser.add_argument("--list-devices", action="store_true", help="Xem danh sách các ngõ ra âm thanh rồi thoát")
    args = parser.parse_args()

    cards = get_alsa_playback_cards()

    if args.list_devices:
        print("\n📋 DANH SÁCH THIẾT BỊ LOA / NGÕ RA ÂM THANH (ALSA):")
        if not cards:
            print("  (Không tìm thấy thiết bị nào qua aplay)")
        for c in cards:
            star = " ★ (Khuyên dùng)" if c["card"] in [1, 2] or "usb" in c["name"].lower() else ""
            print(f"  • Card {c['card']}, Device {c['device']}: {c['name']}{star}")
            print(f"    Chi tiết: {c['raw']}")
        return

    sel_card, sel_dev, sel_name = select_best_playback_device(args.card)
    if args.device != 0:
        sel_dev = args.device

    print(f"""
╔══════════════════════════════════════════════════════════════════════╗
║             🔊 TEST SPEAKER — BỘ KIỂM TRA LOA & ÂM THANH              ║
╠══════════════════════════════════════════════════════════════════════╣
║ • Thiết bị đầu ra      : Card {sel_card}, Dev {sel_dev} ({sel_name:<28})║
║ • Cổng ALSA Target     : plughw:{sel_card},{sel_dev:<38}║
║ • Mức âm lượng         : {int(args.volume * 100)}%                                          ║
╚══════════════════════════════════════════════════════════════════════╝
""")

    # Trường hợp 1: Phát bản thu âm mới nhất từ mic
    if args.latest:
        latest_file = os.path.join(RECORDS_DIR, "latest.wav")
        if not os.path.exists(latest_file):
            # Thử tìm file wav trong test/
            latest_file = os.path.join(PROJECT_ROOT, "test", "recorded_test.wav")
        print(f"🎙️ Phát lại bản thu âm gần nhất: {latest_file}")
        play_wav_file(latest_file, card=sel_card, dev=sel_dev)
        return

    # Trường hợp 2: Phát file wav tùy chọn của người dùng
    if args.file:
        play_wav_file(args.file, card=sel_card, dev=sel_dev)
        return

    # Trường hợp 3: Kiểm tra phân kênh Trái / Phải
    if args.stereo:
        print("🎧 Đang tạo âm thanh kiểm tra 2 kênh stereo...")
        generate_channel_test_wav(TEMP_WAV, volume=args.volume)
        print("👉 Lần lượt: [1] Loa Trái (Left) ──> [2] Loa Phải (Right) ──> [3] Cả 2 loa (Stereo)")
        play_wav_file(TEMP_WAV, card=sel_card, dev=sel_dev)
        return

    # Mặc định: Phát âm Chime 3 nốt nhạc Đô - Mi - Sol nhanh gọn
    print("🔔 Đang phát âm báo chuông kiểm tra nhanh (Chime 3 nốt Đô-Mi-Sol)...")
    generate_chime_wav(TEMP_WAV, volume=args.volume)
    success = play_wav_file(TEMP_WAV, card=sel_card, dev=sel_dev)

    if success:
        print("\n✨ KIỂM TRA HOÀN TẤT: Loa hoạt động tốt!")
        print("💡 Gợi ý thêm:")
        print("  • Kiểm tra 2 kênh Trái/Phải : python test/test_speaker.py --stereo")
        print("  • Nghe lại tiếng mic vừa thu: python test/test_speaker.py --latest")
        print("  • Đổi sang Card âm thanh khác: python test/test_speaker.py --card 0")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n🛑 Đã dừng kiểm thử loa.")


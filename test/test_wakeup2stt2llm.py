"""
====================================================================
  TEST WAKEUP2STT2LLM: KIỂM THỬ TOÀN DIỆN HEY MIRROR ➔ STT ➔ LLM
====================================================================
Luồng hoạt động hoàn chỉnh:
1. [WAKEWORD] Lắng nghe 'Hey Mirror' qua openWakeWord.
2. [VAD THU ÂM] Tự động thu âm câu lệnh và cắt khoảng lặng.
3. [HYBRID STT] Chuyển đổi giọng nói thành văn bản tiếng Việt.
4. [GEMINI NLU ROUTER] Phân loại ý định thông minh & sinh câu trả lời:
   - Action: SMART_HOME, PLAY_MEDIA, SHOW_WEATHER, TAKE_PHOTO, SYSTEM, NONE...
   - Slot Parameters (Thiết bị, bài hát, thành phố...)
   - Phản hồi bằng giọng điệu trợ lý gương thông minh.
5. Hỗ trợ test nhanh bằng văn bản:
   .MMenv/bin/python3 test/test_wakeup2stt2llm.py --text "bật đèn phòng khách"
====================================================================
"""

import argparse
import asyncio
from collections import deque
from datetime import datetime
import json
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
from backend.ai.gemini_router import AIEngine

try:
    import sounddevice as sd
    HAS_SOUNDDEVICE = True
except ImportError:
    sd = None
    HAS_SOUNDDEVICE = False


def select_best_input_device(preferred_idx: Optional[int] = None) -> Optional[int]:
    """Chọn micro tối ưu"""
    if not HAS_SOUNDDEVICE:
        return None
    try:
        devices = []
        for idx, dev in enumerate(sd.query_devices()):
            if dev.get("max_input_channels", 0) > 0:
                devices.append((idx, dev.get("name", f"Device #{idx}")))
        if not devices:
            return None

        if preferred_idx is not None:
            for idx, _ in devices:
                if idx == preferred_idx:
                    return idx

        env_dev = os.getenv("MIC_DEVICE_INDEX")
        if env_dev is not None:
            try:
                env_idx = int(env_dev)
                for idx, _ in devices:
                    if idx == env_idx:
                        return idx
            except Exception:
                pass

        for idx, name in devices:
            if any(k in name.lower() for k in ["usb", "mic", "composite", "pipewire", "pulse", "default"]):
                return idx
        return devices[0][0]
    except Exception:
        return None


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


async def run_llm_pipeline(user_text: str, ai_engine: AIEngine, stt_latency: float = 0.0):
    """Gửi văn bản vào AIEngine và in kết quả chi tiết"""
    print(f"\n🧠 [NLU ROUTER] Đang phân tích ý định câu nói qua Gemini Flash...")
    t0 = time.perf_counter()
    nlu_result = await ai_engine.process_user_input(user_text)
    llm_latency = time.perf_counter() - t0

    action = nlu_result.get("action", "NONE").upper()
    response_text = nlu_result.get("response_text", "")
    query = nlu_result.get("query", "")
    device = nlu_result.get("device", "")
    state = nlu_result.get("state", "")

    total_time = stt_latency + llm_latency

    print("\n" + "═"*75)
    print("🤖 KẾT QUẢ XỬ LÝ TOÀN DIỆN (STT ➔ NLU ➔ AI RESPONSE)")
    print("═"*75)
    print(f"  • 🗣️ Câu nói của bạn      : \"{user_text}\"")
    print(f"  • 🎯 Phân loại Ý định     : [{action}]")
    if query:
        print(f"  • 🔍 Truy vấn / Tìm kiếm   : {query}")
    if device:
        print(f"  • 💡 Thiết bị điều khiển  : {device} (Trạng thái: {state})")
    print(f"  • 💬 Phản hồi của Gương   : \"{response_text}\"")
    print("-" * 75)
    print(f"  ⏱️ Độ trễ STT giải mã      : {stt_latency:.3f}s")
    print(f"  ⏱️ Độ trễ LLM Gemini      : {llm_latency:.3f}s")
    print(f"  ⚡ TỔNG THỜI GIAN TOÀN TRÌNH: {total_time:.3f}s")
    print("═"*75)


async def main_async(args):
    ai_engine = AIEngine()
    ai_mode = "🟢 Gemini Flash API" if ai_engine.is_api_active() else "🟡 Fallback Regex (Chưa có API key)"
    print(f"[🤖 AI Engine] Trạng thái: {ai_mode}")

    # Chế độ kiểm thử nhanh bằng văn bản
    if args.text:
        print(f"\n⌨️ [KIỂM THỬ NHANH BẰNG VĂN BẢN]: '{args.text}'")
        await run_llm_pipeline(args.text, ai_engine, stt_latency=0.0)
        return

    if not HAS_SOUNDDEVICE:
        print("[❌ LỖI] Chưa cài đặt sounddevice. Hãy chạy: pip install sounddevice")
        return

    dev_idx = select_best_input_device(args.device)
    if dev_idx is None:
        print("[❌ LỖI] Không tìm thấy Microphone nào đang kết nối!")
        return

    dev_name = sd.query_devices(dev_idx).get("name", f"Device #{dev_idx}")

    # 1. Khởi tạo Wakeword & STT
    print("⏳ [1/2] Đang nạp mô hình openWakeWord (Hey Mirror)...")
    ww_detector = get_wakeword_detector()
    ww_detector.threshold = args.threshold
    ww_detector.reset()

    print(f"⏳ [2/2] Đang nạp mô hình Hybrid STT (Chế độ: {args.provider.upper()})...")
    stt_engine = get_stt_engine(provider=args.provider)

    SAMPLE_RATE = 16000
    CHUNK_SIZE = 1280
    test_dir = os.path.join(PROJECT_ROOT, "test")
    os.makedirs(test_dir, exist_ok=True)
    wav_path = os.path.join(test_dir, "last_command.wav")

    print(f"""
╔══════════════════════════════════════════════════════════════════════╗
║     🌟 TEST WAKEUP2STT2LLM — TOÀN BỘ CHUỖI TRỢ LÝ THÔNG MINH         ║
╠══════════════════════════════════════════════════════════════════════╣
║ • Microphone đang dùng : [{dev_idx}] {dev_name:<39}║
║ • Ngưỡng Hey Mirror    : {args.threshold*100:5.1f}%                                   ║
║ • Tiền khuếch đại Gain : {args.gain:5.1f}x (Software Pre-amp)                 ║
║ • Bộ giải mã STT       : {args.provider.upper():<44}║
║ • LLM Phân tích Ý định : {ai_mode:<44}║
╠══════════════════════════════════════════════════════════════════════╣
║  👉 Bước 1: Nói "Hey Mirror"                                         ║
║  👉 Bước 2: Nói câu lệnh (ví dụ: "Thời tiết hôm nay thế nào",        ║
║             "Mở bài hát Lạc Trôi", "Bật đèn phòng ngủ"...)           ║
║  👉 Nhấn [Ctrl+C] để thoát                                           ║
╚══════════════════════════════════════════════════════════════════════╝
""")

    STATE_WAIT_WAKE = 0
    STATE_LISTENING = 1
    current_state = STATE_WAIT_WAKE

    speech_buffer = []
    is_speaking = False
    speech_start_time = None
    silence_start_time = None
    listen_start_time = 0.0
    wake_ignore_until = 0.0
    ambient_noise_level = 0.025
    current_dynamic_thresh = args.vad_thresh
    session_count = 0
    current_rms = 0.0
    current_score = 0.0

    loop = asyncio.get_running_loop()

    def audio_callback(indata, frames, time_info, status):
        nonlocal current_rms, current_score, current_state, is_speaking
        nonlocal silence_start_time, speech_start_time, listen_start_time, wake_ignore_until
        nonlocal session_count, ambient_noise_level, current_dynamic_thresh

        now = time.time()
        chunk = indata[:, 0].copy()
        if args.gain != 1.0:
            chunk = np.clip(chunk * args.gain, -1.0, 1.0)

        rms = float(np.sqrt(np.mean(chunk**2)))
        current_rms = rms

        if current_state == STATE_WAIT_WAKE:
            # Thích ứng mức ồn môi trường
            ambient_noise_level = ambient_noise_level * 0.95 + rms * 0.05
            detected, score = ww_detector.process_chunk(chunk)
            current_score = float(score)

            if detected and now >= wake_ignore_until:
                session_count += 1
                current_state = STATE_LISTENING
                listen_start_time = now
                wake_ignore_until = now + 0.65
                speech_buffer.clear()
                is_speaking = False
                speech_start_time = None
                silence_start_time = None
                ww_detector.reset()

                # Tự động tính toán ngưỡng nhạy VAD cao hơn mức ồn phòng
                current_dynamic_thresh = max(args.vad_thresh, ambient_noise_level * 1.55)

                time_str = datetime.now().strftime("%H:%M:%S")
                print(f"\n\n🔥 [{time_str}] [ĐÁNH THỨC THÀNH CÔNG #{session_count}] 'Hey Mirror' (Khớp {score*100:.1f}%)")
                print(f"   🎙️ ➔ [ĐANG LẮNG NGHE] (Ngưỡng VAD: {current_dynamic_thresh:.3f} | Ồn phòng: {ambient_noise_level:.3f})")

        elif current_state == STATE_LISTENING:
            current_score = 0.0
            if now < wake_ignore_until:
                return

            speech_buffer.append(chunk)

            # Ngưỡng bắt đầu nói và ngưỡng giữ nói (Hysteresis)
            voice_start_thresh = current_dynamic_thresh
            voice_hold_thresh = current_dynamic_thresh * 0.70

            if not is_speaking:
                if rms > voice_start_thresh:
                    is_speaking = True
                    speech_start_time = now
                    silence_start_time = None
                else:
                    ambient_noise_level = ambient_noise_level * 0.98 + rms * 0.02
                    current_dynamic_thresh = max(args.vad_thresh, ambient_noise_level * 1.55)
            else:
                speech_dur = now - (speech_start_time or now)

                if rms > voice_hold_thresh:
                    silence_start_time = None
                else:
                    if silence_start_time is None:
                        silence_start_time = now
                    elif (now - silence_start_time) >= args.silence_timeout:
                        # ✅ ĐÃ IM LẶNG VƯỢT QUÁ silence_timeout (0.8s) -> DỨT CÂU NGAY!
                        current_state = STATE_WAIT_WAKE
                        audio_chunks = list(speech_buffer)
                        speech_buffer.clear()
                        is_speaking = False
                        silence_start_time = None
                        speech_start_time = None

                        time_str = datetime.now().strftime("%H:%M:%S")
                        print(f"\n   ✂️ [{time_str}] [NGẮT CÂU THÀNH CÔNG] Đã phát hiện {args.silence_timeout:.2f}s im lặng sau câu nói.")

                        asyncio.run_coroutine_threadsafe(
                            process_full_pipeline(audio_chunks, session_count), loop
                        )
                        return

                if speech_dur >= args.max_duration:
                    current_state = STATE_WAIT_WAKE
                    audio_chunks = list(speech_buffer)
                    speech_buffer.clear()
                    is_speaking = False
                    silence_start_time = None
                    speech_start_time = None

                    print(f"\n   ✂️ [NGẮT CÂU] Đạt giới hạn tối đa {args.max_duration:.1f}s.")
                    asyncio.run_coroutine_threadsafe(
                        process_full_pipeline(audio_chunks, session_count), loop
                    )
                    return

            if (now - listen_start_time) >= 7.0 and not is_speaking:
                print("\n   ⏱️ [HẾT GIỜ] Không nhận được câu lệnh nào.")
                current_state = STATE_WAIT_WAKE
                speech_buffer.clear()
                is_speaking = False
                silence_start_time = None
                speech_start_time = None
                print("\n[✦ SẴN SÀNG] Đang chờ 'Hey Mirror'...")

    async def process_full_pipeline(chunks: List[np.ndarray], s_id: int):
        if not chunks:
            return

        full_audio = np.concatenate(chunks, axis=0)
        dur = len(full_audio) / SAMPLE_RATE
        if dur < 0.30:
            print(f"\n   ⚠️ Âm thanh quá ngắn ({dur:.2f}s), đã bỏ qua.")
            print("\n[✦ SẴN SÀNG] Đang chờ 'Hey Mirror'...")
            return

        save_wav(wav_path, full_audio, SAMPLE_RATE)
        print(f"\n   ⏳ [1/2: STT] Đang giải mã {dur:.2f}s âm thanh qua Hybrid STT...")

        clean_text, stt_lat = await asyncio.to_thread(stt_engine.transcribe_samples, full_audio, SAMPLE_RATE)

        # Lọc biến thể wakeword nếu còn
        for v in ["hey mirror", "hay mirror", "ê mirror", "ê mi rơ", "mirror"]:
            if clean_text.startswith(v):
                clean_text = clean_text[len(v):].strip()

        if not clean_text:
            print(f"\n   ℹ️ (STT không nhận diện được câu nói rõ ràng)")
            print("\n[✦ SẴN SÀNG] Đang chờ 'Hey Mirror'...")
            return

        print(f"   ✅ [STT Hoàn thành trong {stt_lat:.3f}s]: \"{clean_text.upper()}\"")
        # Gửi vào LLM NLU Router
        await run_llm_pipeline(clean_text, ai_engine, stt_latency=stt_lat)
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
            await asyncio.sleep(0.04)


def main():
    default_thresh = float(os.getenv("WAKEWORD_THRESHOLD", "0.65"))
    default_gain = float(os.getenv("MIC_SOFTWARE_GAIN", "2.2"))
    default_vad = float(os.getenv("VAD_VOICE_THRESHOLD", "0.055"))

    parser = argparse.ArgumentParser(description="Kiểm thử toàn bộ chuỗi: Hey Mirror -> STT -> Gemini LLM NLU")
    parser.add_argument("--text", type=str, default=None, help="Nhập trực tiếp câu lệnh text để test nhanh LLM (bỏ qua Mic)")
    parser.add_argument("--device", type=int, default=None, help="Chỉ số index của micro")
    parser.add_argument("--threshold", type=float, default=default_thresh, help=f"Ngưỡng kích hoạt 'Hey Mirror' (mặc định {default_thresh:.2f})")
    parser.add_argument("--gain", type=float, default=default_gain, help=f"Hệ số khuếch đại tiền xử lý mic (mặc định {default_gain:.1f}x)")
    parser.add_argument("--vad-thresh", type=float, default=default_vad, help=f"Ngưỡng nhạy nhận diện giọng nói VAD (mặc định {default_vad:.3f})")
    parser.add_argument("--silence-timeout", type=float, default=0.80, help="Thời gian im lặng để ngắt câu (giây, mặc định 0.80)")
    parser.add_argument("--max-duration", type=float, default=8.0, help="Thời lượng câu lệnh tối đa (giây, mặc định 8.0)")
    parser.add_argument("--provider", type=str, default="auto", choices=["auto", "google", "groq", "gemini", "local"],
                        help="Bộ giải mã STT: auto, google, groq, gemini, local")
    args = parser.parse_args()

    try:
        asyncio.run(main_async(args))
    except KeyboardInterrupt:
        print("\n\n🛑 Đã dừng chương trình kiểm thử.")


if __name__ == "__main__":
    main()


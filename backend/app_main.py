"""
====================================================================
      SMART MIRROR APPLIANCE — MAIN PRODUCTION RUNNER (APP_MAIN)
====================================================================
File điều phối trung tâm (Master Appliance Entry Point):
1. WebSocket Server: ws://0.0.0.0:8085 (Giao tiếp 2 chiều với MagicMirror² UI).
2. Hardware & Drivers:
   - USB Microphone: Thu âm 16kHz, đo RMS phát sóng SiriWave mỗi ~45ms.
   - Pre-amp Gain: Tự động khuếch đại tín hiệu mic yếu (mặc định 3.2x).
   - VAD Thông Minh: Tự động nhận diện mức ồn phòng và ngắt câu sau 0.8s im lặng.
   - USB Camera: OpenCV chụp ảnh chất lượng cao & quét thị giác Gemini Vision.
   - Display Manager: Điều khiển nguồn màn hình phần cứng DPMS (State 0 / 1).
3. AI Voice Pipeline Toàn Diện:
   - Wakeword Engine: openWakeWord nhận diện 'Hey Mirror' tại chỗ (< 20ms).
   - Hybrid STT Engine: Groq Whisper Large v3 (0.25s) ➔ Google Cloud Speech (0.7s)
     ➔ Local Zipformer-30M INT8 Offline Fallback.
   - Gemini NLU Router: Phân loại 10 Action UI & phản hồi giọng điệu trợ lý.
4. Dual Input (Điều khiển song song):
   - Nhận diện giọng nói rảnh tay (Hands-free Voice Input qua Mic).
   - Bàn phím Console: gõ trực tiếp câu lệnh tiếng Việt hoặc phím tắt nhanh.
====================================================================
"""

import argparse
import asyncio
import os
import signal
import sys
import time
from typing import Optional, Tuple

# Đảm bảo UTF-8 trên terminal
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Thêm thư mục gốc dự án vào sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Tự động nạp cấu hình từ .env
env_file = os.path.join(PROJECT_ROOT, ".env")
if os.path.exists(env_file):
    try:
        from dotenv import load_dotenv
        load_dotenv(env_file)
    except ImportError:
        try:
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k, v = k.strip(), v.strip().strip('"').strip("'")
                        if k not in os.environ:
                            os.environ[k] = v
        except Exception:
            pass

from backend.mirror_server import MirrorBackend
from backend.voice.stt_service import get_stt_engine, HybridSTT
from backend.voice.wakeword import get_wakeword_detector, WakeWordDetector


def detect_hardware(cam_index: int = 0, mic_index: Optional[int] = None) -> Tuple[str, str, bool]:
    """Phát hiện chi tiết thông tin phần cứng Microphone và Camera thực tế"""
    mic_name = "Microphone mặc định hệ thống"
    try:
        import sounddevice as sd
        devices = sd.query_devices()
        in_idx = mic_index
        if in_idx is None:
            # Ưu tiên tìm micro USB phần cứng thật
            for idx, dev in enumerate(devices):
                if dev.get("max_input_channels", 0) > 0:
                    name_lower = dev.get("name", "").lower()
                    if any(k in name_lower for k in ["usb", "composite", "webcam", "camera"]):
                        in_idx = idx
                        break
        if in_idx is None:
            in_idx = sd.default.device[0]

        if in_idx is not None and 0 <= in_idx < len(devices):
            d = devices[in_idx]
            name = d.get("name", "Audio Device")
            ch = d.get("max_input_channels", 1)
            mic_name = f"#{in_idx} {name} ({ch} in)"
    except Exception:
        mic_name = f"Microphone (index {mic_index or 0})"

    cam_info = f"Camera index {cam_index} (Chưa mở)"
    cam_ready = False
    try:
        import cv2
        if os.name != "nt":
            cap = cv2.VideoCapture(cam_index, cv2.CAP_V4L2)
        else:
            cap = cv2.VideoCapture(cam_index, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap = cv2.VideoCapture(cam_index)

        if cap.isOpened():
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            cam_info = f"#{cam_index} OpenCV Camera ({w}x{h})"
            cam_ready = True
            cap.release()
        else:
            cam_info = f"#{cam_index} Không mở được camera"
    except Exception as e:
        cam_info = f"#{cam_index} Lỗi: {e}"

    return mic_name, cam_info, cam_ready


def get_stt_description(stt_engine: Optional[HybridSTT]) -> str:
    """Xác định thông tin chuỗi STT đang hoạt động"""
    if not stt_engine:
        return "🔴 Chưa tải được mô hình STT"

    provider = stt_engine.provider.lower()
    if provider == "local":
        return "🟢 Local Zipformer-30M INT8 (100% Offline CPU)"

    if stt_engine.groq_api_key:
        return "🟢 Groq Whisper Large v3 (~0.25s siêu tốc)"
    elif stt_engine.sr_recognizer:
        return "🟢 Google Cloud Speech (~0.7s Free) [Backup: Zipformer-30M]"
    elif stt_engine.gemini_client:
        return "🟢 Gemini Flash Lite Audio [Backup: Zipformer-30M]"
    else:
        return "🟢 Local Zipformer-30M INT8 (Offline)"


def print_banner(
    host: str,
    port: int,
    backend: MirrorBackend,
    stt_engine: Optional[HybridSTT],
    wake_ready: bool,
    mic_name: str,
    cam_info: str,
    cam_ready: bool,
    gain: float,
    wake_thresh: float,
    vad_thresh: float
):
    """In giao diện dashboard tổng quan hệ thống khi khởi động"""
    ai_status = "🟢 Sẵn sàng (Google Gemini Flash API)" if (backend.ai and backend.ai.is_api_active()) else "🟡 Fallback Regex Cục bộ"
    cam_status = f"🟢 {cam_info}" if cam_ready else f"🟡 {cam_info}"
    wake_status = f"🟢 Sẵn sàng (openWakeWord 'Hey Mirror' | Ngưỡng {wake_thresh*100:.0f}%)" if wake_ready else "🔴 Chưa tải được mô hình Wakeword"
    stt_status = get_stt_description(stt_engine)
    disp_status = "🟢 Sẵn sàng (DPMS HDMI Screen Power)" if backend.display else "🟡 Mặc định"

    mic_full_info = f"{mic_name} | Gain: {gain:.1f}x | VAD: {vad_thresh:.3f}"

    print(f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║               🔮 SMART MIRROR 2.0 — APPLIANCE BACKEND SERVER                 ║
╠══════════════════════════════════════════════════════════════════════════════╣
║ • WebSocket Server : ws://{host}:{port:<5}                                          ║
║ • Microphone Thật  : {mic_full_info:<55}║
║ • Camera Hardware  : {cam_status:<55}║
║ • Wakeword Engine  : {wake_status:<55}║
║ • Speech-to-Text   : {stt_status:<55}║
║ • NLU Router (AI)  : {ai_status:<55}║
║ • Màn hình Gương   : {disp_status:<55}║
╠══════════════════════════════════════════════════════════════════════════════╣
║ [🎙️ Hands-Free Mic] Hô 'Hey Mirror' rồi nói câu lệnh tiếng Việt tự nhiên.     ║
║ [⌨️ Console Input] Bạn cũng có thể gõ câu lệnh vào đây rồi nhấn Enter.        ║
║ [⌨️ Phím tắt nhanh] '0': Ngủ | '1': Thức | 'p': Chụp ảnh | 'c': Quét camera   ║
║                    'm': Bật nhạc | 'w': Xem ảnh | 'wake': Hey Mirror | 'q': Thoát ║
╚══════════════════════════════════════════════════════════════════════════════╝
""")


async def console_input_loop(backend: MirrorBackend, stop_event: asyncio.Event):
    """Vòng lặp nhận lệnh từ bàn phím console (khi chạy có terminal TTY)"""
    if not sys.stdin.isatty():
        return

    def read_line() -> str:
        try:
            return sys.stdin.readline().strip()
        except Exception:
            return ""

    while not stop_event.is_set():
        cmd = await asyncio.to_thread(read_line)
        if stop_event.is_set():
            break
        if not cmd:
            continue

        cmd_lower = cmd.lower()

        if cmd_lower in ["q", "quit", "exit"]:
            print("\n[🛑 Người dùng yêu cầu dừng] Đang đóng ứng dụng...")
            stop_event.set()
            break
        elif cmd_lower == "0":
            print(">>> [Phím tắt] Chuyển gương sang State 0 (Ngủ / Màn hình tắt đen)...")
            await backend.set_sleep()
        elif cmd_lower == "1":
            print(">>> [Phím tắt] Chuyển gương sang State 1 (Thức / Màn hình bật sáng)...")
            await backend.set_active()
        elif cmd_lower in ["wake", "hey mirror", "k"]:
            print(">>> [Phím tắt] Giả lập sự kiện đánh thức 'Hey Mirror'...")
            await backend.handle_wakeword_triggered(score=1.0)
        elif cmd_lower == "p":
            if backend.photo_mode_active:
                print(">>> [Phím tắt] Bắt đầu đếm ngược 3s chụp ảnh webcam...")
                await backend.start_photo_countdown(countdown=3)
            else:
                print(">>> [Phím tắt] Mở camera soi gương tạo dáng...")
                await backend.open_photo_preview()
        elif cmd_lower in ["x", "cancel", "huy"]:
            print(">>> [Phím tắt] Hủy chụp ảnh / đóng camera preview...")
            await backend.cancel_photo_mode()
        elif cmd_lower == "c":
            print(">>> [Phím tắt] Chụp webcam và quét phân tích thị giác (Vision AI)...")
            await backend.search_camera_vision()
        elif cmd_lower == "m":
            print(">>> [Phím tắt] Thử phát bài hát mẫu...")
            await backend.handle_user_prompt("Bật bài Nơi này có anh")
        elif cmd_lower == "w":
            print(">>> [Phím tắt] Thử tìm ảnh con mèo...")
            await backend.handle_user_prompt("Cho tôi xem ảnh con mèo")
        elif cmd_lower == "h":
            print(">>> [Phím tắt] Thử bật đèn phòng khách...")
            await backend.handle_user_prompt("Bật đèn phòng khách")
        elif cmd_lower == "stt":
            stt_engine = get_stt_engine()
            desc = get_stt_description(stt_engine)
            print(f">>> [Trạng thái STT] {desc}")
        else:
            # Gõ câu tự nhiên -> chuyển vào pipeline Gemini NLU Router
            await backend.handle_user_prompt(cmd)


async def run_app(args):
    """Vòng lặp chính quản lý vòng đời ứng dụng Smart Mirror"""
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    # Thiết lập biến môi trường phần cứng & âm thanh
    if args.cam_index is not None:
        os.environ["CAMERA_INDEX"] = str(args.cam_index)
    if args.mic_index is not None:
        os.environ["MIC_DEVICE_INDEX"] = str(args.mic_index)
    if args.gain is not None:
        os.environ["MIC_SOFTWARE_GAIN"] = str(args.gain)
    if args.threshold is not None:
        os.environ["WAKEWORD_THRESHOLD"] = str(args.threshold)
    if args.vad_thresh is not None:
        os.environ["VAD_VOICE_THRESHOLD"] = str(args.vad_thresh)
    if args.provider is not None:
        os.environ["STT_PROVIDER"] = str(args.provider)

    active_gain = float(os.getenv("MIC_SOFTWARE_GAIN", "3.2"))
    active_wake_thresh = float(os.getenv("WAKEWORD_THRESHOLD", "0.55"))
    active_vad_thresh = float(os.getenv("VAD_VOICE_THRESHOLD", "0.055"))

    # 1. Khởi tạo Backend Server (WebSocket 8085)
    backend = MirrorBackend(host=args.host, port=args.port)
    await backend.start_server()

    # 2. Kiểm tra phần cứng
    mic_name, cam_info, cam_ready = detect_hardware(cam_index=args.cam_index, mic_index=args.mic_index)

    # 3. Kiểm tra mô hình STT & Wakeword
    stt_engine = get_stt_engine(provider=args.provider)
    wakeword_engine = get_wakeword_detector()
    wake_ready = bool(wakeword_engine and wakeword_engine.is_ready)
    if wakeword_engine:
        wakeword_engine.threshold = active_wake_thresh

    # 4. In Dashboard Banner tổng quan
    print_banner(
        args.host, args.port, backend, stt_engine, wake_ready,
        mic_name, cam_info, cam_ready, active_gain, active_wake_thresh, active_vad_thresh
    )

    # 5. Đặt trạng thái ban đầu của gương
    initial_state = int(args.initial_state)
    await backend.set_state(initial_state, text="Hệ thống đã khởi động", sub_state="idle")

    # 6. Bật micro thu âm thật, Wakeword & STT thời gian thực
    mic_started = backend.start_real_mic(
        sensitivity=args.sensitivity,
        enable_stt=args.enable_stt,
        enable_wakeword=args.enable_wakeword,
        enable_live_display=args.enable_live_display
    )
    if mic_started:
        print(f"[🎤 Micro Sẵn Sàng] Đang phát sóng SiriWave & tự động lắng nghe từ khóa 'Hey Mirror' rảnh tay.")
        print("\n[✦ SẴN SÀNG] Đang chờ bạn nói 'Hey Mirror'...\n")
    else:
        print("[⚠️ Micro Chưa Sẵn Sàng] Chưa mở được Microphone. Hãy kiểm tra kết nối mic USB.")

    # 7. Xử lý tín hiệu tắt an toàn (Graceful Shutdown)
    def handle_shutdown_signal(sig_name):
        print(f"\n[🛑 Shutdown] Nhận tín hiệu {sig_name}. Đang đóng hệ thống an toàn...")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda s=sig.name: handle_shutdown_signal(s))
        except NotImplementedError:
            pass

    # 8. Khởi chạy luồng đọc console song song
    input_task = asyncio.create_task(console_input_loop(backend, stop_event))

    # Chờ sự kiện dừng
    try:
        await stop_event.wait()
    except (asyncio.CancelledError, KeyboardInterrupt):
        print("\n[🛑 Shutdown] Nhận ngắt bàn phím (Ctrl+C). Đang đóng ứng dụng...")
    finally:
        input_task.cancel()

        print("[...] Đang dừng micro...")
        backend.stop_real_mic()

        print("[...] Đang đóng máy chủ mạng...")
        if hasattr(backend, "stop_server"):
            await backend.stop_server()

        print("[...] Đang giải phóng camera...")
        if backend.camera:
            backend.camera.release()

        print("[...] Đang khôi phục màn hình bảo vệ...")
        if backend.display:
            backend.display.turn_on()

        print("[✅ Hoàn tất] Backend Smart Mirror đã tắt an toàn.")


def main():
    default_gain = float(os.getenv("MIC_SOFTWARE_GAIN", "3.2"))
    default_wake = float(os.getenv("WAKEWORD_THRESHOLD", "0.55"))
    default_vad = float(os.getenv("VAD_VOICE_THRESHOLD", "0.055"))
    default_provider = os.getenv("STT_PROVIDER", "auto")

    parser = argparse.ArgumentParser(description="Smart Mirror 2.0 Backend Master Appliance Runner")
    parser.add_argument("--host", default=os.getenv("BACKEND_HOST", "0.0.0.0"), help="WebSocket Host (mặc định 0.0.0.0)")
    parser.add_argument("--port", type=int, default=int(os.getenv("BACKEND_PORT", "8085")), help="WebSocket Port (mặc định 8085)")
    parser.add_argument("--cam-index", type=int, default=int(os.getenv("CAMERA_INDEX", "0")), help="Camera device index (mặc định 0)")
    parser.add_argument("--mic-index", type=int, default=int(os.getenv("MIC_DEVICE_INDEX")) if os.getenv("MIC_DEVICE_INDEX") else None, help="Microphone device index (mặc định None - tự động chọn)")
    parser.add_argument("--gain", type=float, default=default_gain, help=f"Hệ số tiền khuếch đại mic (mặc định {default_gain:.1f}x)")
    parser.add_argument("--threshold", type=float, default=default_wake, help=f"Ngưỡng kích hoạt 'Hey Mirror' (mặc định {default_wake:.2f})")
    parser.add_argument("--vad-thresh", type=float, default=default_vad, help=f"Ngưỡng nhạy VAD (mặc định {default_vad:.3f})")
    parser.add_argument("--provider", type=str, default=default_provider, choices=["auto", "google", "groq", "gemini", "local"],
                        help="Bộ giải mã STT: auto (khuyên dùng), google, groq, gemini, local (Zipformer-30M)")
    parser.add_argument("--sensitivity", type=float, default=float(os.getenv("MIC_SENSITIVITY", "12.0")), help="Độ nhạy biên độ sóng Siri (mặc định 12.0)")
    parser.add_argument("--initial-state", type=int, default=int(os.getenv("INITIAL_STATE", "1")), help="Trạng thái ban đầu: 1 (Active) hoặc 0 (Sleep)")
    parser.add_argument("--enable-wakeword", action="store_true", default=True, help="Bật nhận diện từ khóa 'Hey Mirror'")
    parser.add_argument("--no-wakeword", dest="enable_wakeword", action="store_false", help="Tắt nhận diện từ khóa 'Hey Mirror'")
    parser.add_argument("--enable-stt", action="store_true", default=True, help="Bật nhận dạng giọng nói STT")
    parser.add_argument("--no-stt", dest="enable_stt", action="store_false", help="Tắt nhận dạng giọng nói STT")
    parser.add_argument("--no-live-bar", dest="enable_live_display", action="store_false", default=True,
                        help="Tắt thanh trạng thái trực quan VU Meter / Confidence Bar trên console")

    args = parser.parse_args()

    try:
        asyncio.run(run_app(args))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()

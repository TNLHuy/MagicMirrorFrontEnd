"""
====================================================================
      CLI CONTROLLER PYTHON - ĐIỀU KHIỂN TƯƠNG TÁC 10 ACTION NLU
      (TÍCH HỢP GEMINI AI NLU ROUTER + CAMERA + MICRO + BUBBLE)
====================================================================
Cho phép bạn:
1. Gõ bất kỳ câu nói tiếng Việt nào -> AI Engine (Gemini 3.8 Flash)
   sẽ tự động hiểu ý định (Intent), phân loại Action và kích hoạt màn hình!
2. Hoặc sử dụng các phím tắt nhanh để test từng Action theo ý muốn.
====================================================================
"""

import asyncio
import sys

# Đảm bảo UTF-8 trên Windows console
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from backend.mirror_server import MirrorBackend

def print_menu(ai_status: bool = False):
    status_str = "🟢 ĐÃ KÍCH HOẠT (Gemini 3.8 Flash)" if ai_status else "🟡 CHẾ ĐỘ NỘI BỘ (Nhập 'key <API_KEY>' để bật Gemini)"
    print(f"""
====================================================================
      BỘ ĐIỀU KHIỂN NLU ROUTER & TRỢ LÝ AI (PYTHON CLI)
      Trạng thái AI: {status_str}
====================================================================
 [CÁCH 1: NÓI TRỰC TIẾP VÀO MICROPHONE (KHÔNG CẦN CHẠM BÀN PHÍM)]
  🎙️ Hệ thống đang lắng nghe bạn nói theo thời gian thực!
  Hãy thử cất tiếng nói trước máy tính:
   • "Hey Mirror"                     -> Đánh thức màn hình (State 1) & mở nghe lệnh!
   • "Chụp cho tôi một bức ảnh"       -> Tự động đếm ngược 3s + chụp webcam!
   • "Bật đèn phòng khách"            -> Tự động bật đèn SmartHome!
   • "Bây giờ là mấy giờ?"            -> Trả lời giờ trong Bubble thủy tinh!
   • "Hôm nay thời tiết thế nào?"     -> Dự báo thời tiết!
   • "Mở bài hát Nơi này có anh"      -> Tự động phát nhạc!
   • "Chào bạn, bạn có thể làm gì?"   -> Trò chuyện với Gemini AI!
   • "Tắt màn hình đi ngủ"            -> Tắt gương chuyển State 0 (Ngủ)!

 [CÁCH 2: GÕ CÂU LỆNH TỰ NHIÊN VÀO TERMINAL (TÙY CHỌN)]
  Gõ bất kỳ câu nào rồi nhấn Enter -> Gemini AI xử lý ngay.

 [CÁCH 3: PHÍM TẮT TEST TỪNG ACTION NHANH]
  [0]    : State 0 (Ngủ / Tắt màn hình)
  [1]    : State 1 (Thức / Hiện Widget tĩnh 4 góc)
  [wake] : Test nhanh sự kiện đánh thức 'Hey Mirror' (Dành cho khi chưa cắm Micro)
  [mic]  : BẬT / TẮT Microphone & Nhận diện giọng nói
  [p]    : Action TAKE_PHOTO (Mở camera soi gương tạo dáng -> Nhấn lại 'p' hoặc nói 'chụp ảnh' để chụp)
  [x]    : Hủy chụp ảnh / Tắt camera khi đang chờ tạo dáng
  [c]    : Action SEARCH (camera) (Chụp webcam + Quét thị giác Vision AI)
  [s]    : Action NONE (Hiện bong bóng thủy tinh Bubble trả lời)
  [w]    : Action SEARCH (web_image) (Popup ảnh tìm kiếm web)
  [m]    : Action PLAY_MEDIA (Trình phát nhạc mini)
  [h]    : Action SMART_HOME (Thiết bị thông minh)
  [i]    : Action IDLE (Đóng popup ở trung tâm gương)
  [key <API_KEY>] : Nhập Google Gemini API Key mới
  [?]    : Xem lại menu hướng dẫn
  [q]    : Thoát chương trình
====================================================================
""")

async def main():
    backend = MirrorBackend(host="0.0.0.0", port=8085)
    await backend.start_server()

    # Kích hoạt micro thật, nhận diện từ khóa 'Hey Mirror' & Speech-to-Text tiếng Việt tự động
    mic_active = backend.start_real_mic(sensitivity=12.0, enable_stt=True, enable_wakeword=True)
    if mic_active:
        print("[🎤 Micro] Đã kích hoạt thu âm, Nhận diện 'Hey Mirror' & Nhận dạng giọng nói tiếng Việt tự động!")
    else:
        print("[ℹ️ Micro] Chưa mở được Micro (khi cắm mic USB vào máy, micro sẽ tự động sẵn sàng).")

    ai_active = backend.ai.is_api_active() if backend.ai else False
    print_menu(ai_active)

    def get_input():
        try:
            return sys.stdin.readline().strip()
        except Exception:
            return "q"

    while True:
        cmd = await asyncio.to_thread(get_input)
        if not cmd:
            continue

        cmd_lower = cmd.lower()

        # 1. Quản lý API Key
        if cmd_lower.startswith("key ") or cmd_lower.startswith("apikey "):
            parts = cmd.split(maxsplit=1)
            if len(parts) > 1 and backend.ai:
                backend.ai.set_api_key(parts[1].strip())
                ai_active = backend.ai.is_api_active()
                if ai_active:
                    print("\n[✅ Thành công] Đã kích hoạt Google Gemini 3.8 Flash API!")
                else:
                    print("\n[!] Không thể kích hoạt API với key vừa nhập.")
                continue

        # 2. Các phím tắt nhanh
        if cmd_lower == "0":
            await backend.set_sleep()
        elif cmd_lower == "1":
            await backend.set_active()
        elif cmd_lower in ["wake", "hey mirror", "k"]:
            print(">>> [TEST WAKEWORD] Giả lập phát hiện từ khóa 'Hey Mirror'...")
            await backend.handle_wakeword_triggered(score=0.98)
        elif cmd_lower == "l":
            await backend.ai_listen("Đang lắng nghe bạn nói...")
        elif cmd_lower == "mic":
            if backend.mic and backend.mic.is_running:
                backend.stop_real_mic()
                print("[🎤 Micro] Đã TẮT Microphone.")
            else:
                if backend.start_real_mic(sensitivity=12.0):
                    print("[🎤 Micro] Đã BẬT Microphone thật! Hãy thử nói vào micro.")
                else:
                    print("[!] Không thể bật Microphone.")
        elif cmd_lower == "v":
            print(">>> Đang giả lập giọng nói rung sóng trong 4 giây...")
            await backend.stream_voice_simulation(duration_sec=4.0, base=0.45, noise=0.55)
            print(">>> Hoàn tất.")
        elif cmd_lower == "s":
            print("Nhập câu trả lời hiển thị trong Bong bóng Bubble (nhấn Enter để dùng mặc định):")
            text = await asyncio.to_thread(get_input)
            if not text:
                text = "Xin chào! Bây giờ là 20:00, thời tiết TP.HCM 28°C rất mát mẻ và dễ chịu."
            await backend.ai_speak(text)
        elif cmd_lower == "w":
            print("Nhập tên thực thể/con vật/địa danh muốn xem ảnh & tri thức (Enter để dùng 'con trâu'):")
            q_input = await asyncio.to_thread(get_input)
            if not q_input:
                q_input = "con trâu"
            await backend.handle_user_prompt(f"cho tôi xem ảnh {q_input}")
        elif cmd_lower == "c":
            print(">>> Đang chụp ảnh webcam thật và quét phân tích thị giác...")
            await backend.search_camera_vision()
        elif cmd_lower == "p":
            if backend.photo_mode_active:
                print(">>> Nhận lệnh 'chụp'! Bắt đầu đếm ngược 3 giây...")
                await backend.start_photo_countdown(countdown=3)
            else:
                print(">>> Đang mở Camera Live Preview ở trạng thái chờ tạo dáng...")
                await backend.open_photo_preview()
        elif cmd_lower in ["x", "cancel", "huy"]:
            if backend.photo_mode_active:
                print(">>> Nhận lệnh 'hủy'! Đang tắt camera...")
                await backend.cancel_photo_mode()
            else:
                await backend.ai_idle()
        elif cmd_lower == "m":
            await backend.play_media(
                title="Nơi Này Có Anh",
                artist="Sơn Tùng M-TP",
                state="playing",
                response_text="Đang phát bài hát: Nơi Này Có Anh"
            )
        elif cmd_lower == "h":
            await backend.update_smart_home(
                devices=[
                    {"name": "Đèn phòng khách", "status": "ON"},
                    {"name": "Máy lạnh", "status": "24°C"},
                    {"name": "Cửa chính", "status": "LOCKED"}
                ],
                response_text="Đã cập nhật thiết bị nhà thông minh."
            )
        elif cmd_lower == "i":
            await backend.ai_idle()
        elif cmd_lower in ["?", "help"]:
            ai_active = backend.ai.is_api_active() if backend.ai else False
            print_menu(ai_active)
        elif cmd_lower == "q":
            if backend.mic:
                backend.stop_real_mic()
            print("Tạm biệt!")
            break
        else:
            # 3. Xử lý câu lệnh tự nhiên qua Gemini NLU Router
            await backend.handle_user_prompt(cmd)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nĐã thoát chương trình.")
        sys.exit(0)

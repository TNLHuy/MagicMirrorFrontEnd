"""
====================================================================
          TEST LLM: KIỂM THỬ TRÍ TUỆ NHÂN TẠO & NLU ROUTER
====================================================================
Chức năng:
1. Kiểm thử độc lập bộ não AI Google Gemini (hoặc Fallback Regex).
2. Phân loại ý định (Action) và trích xuất tham số (Entities / Slots).
3. Sinh câu phản hồi thông minh tự nhiên của Trợ lý Gương MagicMirror.

Cách sử dụng:
1. Chế độ trò chuyện tương tác (Interactive REPL - Mặc định):
   .MMenv/bin/python3 test/test_llm.py

2. Chạy 1 câu lệnh đơn qua tham số:
   .MMenv/bin/python3 test/test_llm.py --prompt "Bật đèn phòng khách"
   .MMenv/bin/python3 test/test_llm.py --prompt "Mở nhạc Sơn Tùng M-TP"
   .MMenv/bin/python3 test/test_llm.py --prompt "Thời tiết Hà Nội hôm nay thế nào"

3. Chạy toàn bộ bộ test mẫu tự động (Test Suite 10 Actions):
   .MMenv/bin/python3 test/test_llm.py --suite
====================================================================
"""

import argparse
import asyncio
from datetime import datetime
import json
import os
import sys
import time
from typing import Dict, Any, List

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

from backend.ai.gemini_router import AIEngine


ACTION_DESCRIPTIONS = {
    "NONE": "Hội thoại AI thông thường (Bong bóng lời nói / Chat)",
    "SMART_HOME": "Điều khiển thiết bị nhà thông minh (Đèn, quạt, công tắc...)",
    "PLAY_MEDIA": "Phát nhạc / Media qua YouTube / Mini Player",
    "SHOW_WEATHER": "Dự báo thời tiết & nhiệt độ",
    "TAKE_PHOTO": "Kích hoạt Camera đếm ngược 3s và chụp ảnh",
    "GET_TIME": "Hỏi thời gian / Giờ hiện tại",
    "GET_DATE": "Hỏi ngày tháng / Lịch vạn niên",
    "GET_CALENDAR": "Xem lịch trình công việc / Sự kiện Google Calendar",
    "SEARCH": "Tìm kiếm hình ảnh hoặc quét thị giác Camera",
    "SYSTEM": "Lệnh hệ thống: Đi ngủ (tắt màn hình), Thức dậy, Âm lượng",
}


def print_nlu_result(user_text: str, result: Dict[str, Any], latency: float, verbose: bool = False):
    """In định dạng kết quả NLU chi tiết, đẹp mắt"""
    action = str(result.get("action", "NONE")).upper()
    response_text = result.get("response_text", "")
    desc = ACTION_DESCRIPTIONS.get(action, "Ý định tùy biến")

    # Thu thập các tham số trích xuất được (Slots)
    slots = {}
    for k, v in result.items():
        if k not in ["action", "response_text"] and v is not None and v != "":
            slots[k] = v

    print("\n" + "═" * 75)
    print(f"🤖 KẾT QUẢ PHÂN TÍCH NLU (Thời gian xử lý: {latency:.3f}s)")
    print("═" * 75)
    print(f"  • 🗣️ Câu nói đầu vào  : \"{user_text}\"")
    print(f"  • 🎯 Phân loại Ý định : [{action}] ➔ {desc}")
    if slots:
        print(f"  • 📦 Tham số trích xuất:")
        for sk, sv in slots.items():
            print(f"      - {sk:<12}: {sv}")
    print(f"  • 💬 Phản hồi của Gương: \"{response_text}\"")

    if verbose:
        print("-" * 75)
        print("  • 📄 Raw JSON:")
        print("    " + json.dumps(result, ensure_ascii=False, indent=4).replace("\n", "\n    "))

    print("═" * 75)


async def test_single_prompt(ai: AIEngine, text: str, verbose: bool = False):
    """Xử lý 1 câu prompt đơn lẻ"""
    t0 = time.perf_counter()
    result = await ai.process_user_input(text)
    latency = time.perf_counter() - t0
    print_nlu_result(text, result, latency, verbose=verbose)


async def run_test_suite(ai: AIEngine, verbose: bool = False):
    """Chạy bộ kiểm thử 10 trường hợp mẫu đại diện cho 10 Actions của Gương"""
    test_cases = [
        ("Bật đèn phòng khách giúp tôi", "SMART_HOME"),
        ("Tắt quạt trần đi", "SMART_HOME"),
        ("Mở bài hát Lạc Trôi của Sơn Tùng", "PLAY_MEDIA"),
        ("Thời tiết Hà Nội hôm nay thế nào", "SHOW_WEATHER"),
        ("Bây giờ là mấy giờ rồi", "GET_TIME"),
        ("Hôm nay là ngày bao nhiêu", "GET_DATE"),
        ("Chụp cho tôi một bức ảnh kỷ niệm", "TAKE_PHOTO"),
        ("Gương ơi đi ngủ thôi", "SYSTEM"),
        ("Cho tôi xem hình ảnh tháp Eiffel", "SEARCH"),
        ("Bạn là ai và có thể giúp gì cho tôi", "NONE"),
    ]

    print("\n" + "=" * 75)
    print(f"🚀 BẮT ĐẦU CHẠY BỘ KIỂM THỬ NLU ROUTER ({len(test_cases)} TRƯỜNG HỢP)")
    print("=" * 75)

    passed_count = 0
    total_latency = 0.0

    for idx, (prompt, expected_action) in enumerate(test_cases, 1):
        print(f"\n[{idx:2d}/{len(test_cases)}] Đang test: \"{prompt}\"")
        t0 = time.perf_counter()
        result = await ai.process_user_input(prompt)
        lat = time.perf_counter() - t0
        total_latency += lat

        action = str(result.get("action", "NONE")).upper()
        is_match = (action == expected_action)
        if is_match:
            passed_count += 1
            status_mark = "✅ KHỚP"
        else:
            status_mark = f"⚠️ KHÁC (Mong đợi: {expected_action})"

        resp_text = result.get("response_text", "")
        print(f"    ➔ Ý định: [{action}] ({status_mark}) | Độ trễ: {lat:.3f}s")
        print(f"    ➔ Phản hồi: \"{resp_text}\"")

    avg_lat = total_latency / len(test_cases)
    print("\n" + "=" * 75)
    print(f"📊 TỔNG KẾT BỘ KIỂM THỬ: {passed_count}/{len(test_cases)} khớp chính xác")
    print(f"⏱️ Thời gian trung bình mỗi câu: {avg_lat:.3f}s")
    print("=" * 75)


async def interactive_chat_loop(ai: AIEngine, verbose: bool = False):
    """Vòng lặp tương tác trò chuyện trực tiếp từ bàn phím terminal"""
    print("""
╔══════════════════════════════════════════════════════════════════════╗
║             🧠 TEST LLM — TRÒ CHUYỆN TƯƠNG TÁC VỚI AI                ║
╠══════════════════════════════════════════════════════════════════════╣
║ • Nhập bất kỳ câu lệnh hoặc câu hỏi nào để AI phân loại & trả lời     ║
║ • Ví dụ: "Bật đèn", "Mở nhạc", "Mấy giờ rồi", "Thời tiết hôm nay"... ║
║ • Gõ 'q' hoặc 'exit' để thoát                                        ║
╚══════════════════════════════════════════════════════════════════════╝
""")
    loop = asyncio.get_running_loop()
    while True:
        try:
            # Đọc input bất đồng bộ để không chặn event loop
            user_input = await loop.run_in_executor(None, input, "\n💬 Nhập câu lệnh: ")
            user_input = user_input.strip()

            if not user_input:
                continue

            if user_input.lower() in ["q", "exit", "quit"]:
                print("\n👋 Đã thoát kiểm thử LLM.")
                break

            await test_single_prompt(ai, user_input, verbose=verbose)

        except (KeyboardInterrupt, EOFError):
            print("\n\n👋 Đã dừng kiểm thử.")
            break


async def main_async():
    parser = argparse.ArgumentParser(description="Kiểm thử độc lập bộ não AI & NLU Router của Smart Mirror")
    parser.add_argument("--prompt", type=str, default=None, help="Câu lệnh đơn cần kiểm thử")
    parser.add_argument("--suite", action="store_true", help="Chạy bộ test mẫu tự động 10 trường hợp")
    parser.add_argument("--verbose", action="store_true", help="In toàn bộ dữ liệu JSON chi tiết")
    args = parser.parse_args()

    ai = AIEngine()
    ai_status = "🟢 Google Gemini Flash API (Online)" if ai.is_api_active() else "🟡 Fallback Regex Cục bộ (Offline)"
    print(f"\n🔮 [SMART MIRROR AI ENGINE] Trạng thái: {ai_status}")

    if args.suite:
        await run_test_suite(ai, verbose=args.verbose)
    elif args.prompt:
        await test_single_prompt(ai, args.prompt, verbose=args.verbose)
    else:
        await interactive_chat_loop(ai, verbose=args.verbose)


def main():
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()


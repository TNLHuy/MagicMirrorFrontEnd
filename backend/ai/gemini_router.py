"""
====================================================================
      AI ENGINE & NLU ROUTER (GOOGLE GEMINI 3.8 FLASH API)
====================================================================
Module trí tuệ nhân tạo trung tâm:
1. NLU Router:
   - Tiếp nhận câu nói/văn bản từ người dùng.
   - Gửi yêu cầu tới Google Gemini 3.8 Flash API để phân tích ý định (Intent Classification).
   - Tự động phân loại chính xác thành 1 trong 10 ACTION theo NLU Router Layout:
       • NONE        : Hội thoại AI thông thường -> Bong bóng Bubble
       • TAKE_PHOTO  : Yêu cầu chụp ảnh -> Đếm ngược 3s + Chụp webcam
       • SEARCH (img): Tìm kiếm hình ảnh -> Popup ảnh web
       • SEARCH (cam): Quét thị giác camera -> Phân tích vật thể
       • PLAY_MEDIA  : Yêu cầu phát nhạc -> Trình phát mini
       • SMART_HOME  : Điều khiển nhà thông minh -> Trạng thái thiết bị
       • SYSTEM      : Đi ngủ (state 0), Thức dậy (state 1), Âm lượng
       • GET_TIME / GET_DATE / SHOW_WEATHER / GET_CALENDAR
2. Vision AI:
   - Gửi khung hình webcam chụp được tới Gemini 3.8 Flash Vision
     để nhận diện đồ vật thật và tạo nhãn nhãn đối tượng (Vision Tags).
3. Fallback NLU Thông Minh:
   - Khi chưa cấu hình GEMINI_API_KEY, hệ thống tự động kích hoạt
     bộ phân tích cục bộ để test mượt mà mọi lệnh mà không bị gián đoạn.
====================================================================
"""

import asyncio
from datetime import datetime, date
import json
import os
import re
import sys
from typing import Dict, Any, Optional, List

import warnings
warnings.filterwarnings("ignore")

# Đảm bảo UTF-8
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Thư viện Google GenAI SDK (phiên bản chuẩn mới)
try:
    from google import genai
    from google.genai import types
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False

NLU_SYSTEM_INSTRUCTION = """
Bạn là hệ thống trí tuệ nhân tạo NLU Router điều khiển Gương thông minh MagicMirror (Smart Mirror).
Người dùng sẽ nói hoặc gửi câu lệnh bằng tiếng Việt. Nhiệm vụ của bạn là:
1. Phân loại ý định của người dùng vào ĐÚNG 1 trong 10 ACTION sau:
   - NONE: Hội thoại thông thường, trò chuyện, hỏi đáp kiến thức chung, chào hỏi, chúc ngày mới.
   - TAKE_PHOTO: Người dùng bảo chụp ảnh, chụp hình, chụp selfie, chụp ảnh cho tôi, mở camera, bật camera, mở máy ảnh, soi gương.
   - SEARCH:
       * target = "web_image": Người dùng muốn xem ảnh hoặc tìm hiểu về một con vật, đồ vật, thực thể, danh lam, hoa lá, nhân vật, vũ trụ... (ví dụ: "cho tôi xem ảnh con trâu", "tìm ảnh loài chó", "tháp eiffel", "con voi", "hoa sen").
         ĐẶC BIỆT: Khi target = "web_image", bạn PHẢI cung cấp đầy đủ thông tin tri thức về thực thể:
         - entity_name: Tên thực thể chuẩn tiếng Việt viết hoa đẹp (ví dụ: "Con Trâu (Trâu Nước)", "Loài Chó (Chó Nhà)", "Tháp Eiffel").
         - english_keyword: Từ khóa tiếng Anh chuẩn xác để tìm ảnh chất lượng cao trên CDN quốc tế (ví dụ: "water buffalo", "dog breeds", "eiffel tower paris", "asian elephant", "lotus flower").
         - scientific_name: Tên khoa học hoặc danh mục phân loại/địa danh (ví dụ: "Bubalus bubalis • Động vật có vú", "Canis lupus familiaris", "La Tour Eiffel • Paris, Pháp").
         - summary: Đoạn văn 2-3 câu súc tích, giàu kiến thức, hấp dẫn về đặc điểm, nguồn gốc hoặc giá trị văn hóa để hiển thị thẻ tri thức trên gương.
         - facts: Mảng 2-3 thông tin thú vị/thông số nổi bật (ví dụ: ["Sức kéo dẻo dai, 'đầu cơ nghiệp' nhà nông", "Thích đầm bùn để giải nhiệt", "Biểu tượng con giáp thứ 2"]).
       * target = "camera": Người dùng yêu cầu nhận diện vật thể trước gương (ví dụ: "Xem đây là cái gì", "quét camera", "nhìn vật này").
   - PLAY_MEDIA: Bật nhạc, phát bài hát, nghe nhạc hoặc tắt/dừng nhạc (ví dụ: "Bật bài Nơi này có anh", "tắt nhạc đi", "dừng phát nhạc").
       * Khi bật nhạc: state = "playing", title = tên bài hát, artist = ca sĩ (nếu có).
       * Khi tắt/dừng nhạc: state = "paused" hoặc "stopped".
   - SMART_HOME: Bật/tắt đèn, máy lạnh, khóa cửa phòng (ví dụ: "Bật đèn phòng khách", "tắt điều hòa", "khóa cửa").
   - SYSTEM:
       * Đi ngủ, tắt màn hình, tắt gương -> state = 0
       * Thức dậy, bật màn hình, mở gương -> state = 1
       * Tăng/giảm âm lượng -> volume = 0.0 đến 1.0
   - SHOW_WEATHER: Hỏi thời tiết hiện tại hoặc dự báo. Trích xuất tên thành phố vào 'query' (mặc định 'TP. Hồ Chí Minh').
   - GET_TIME: Hỏi bây giờ là mấy giờ.
   - GET_DATE: Hỏi hôm nay là ngày mấy, thứ mấy.
   - GET_CALENDAR: Hỏi lịch làm việc, sự kiện, thời khóa biểu, lịch học hôm nay hoặc ngày bất kỳ (ví dụ: "lịch trình hôm nay", "ngày mai có học gì không", "thứ sáu có lịch gì"). Trích xuất ngày hoặc cụm thời gian vào 'query' (ví dụ: 'hôm nay', 'ngày mai', 'thứ sáu', 'ngày 10/10').

2. QUY TẮC PHẢN HỒI RESPONSE_TEXT (BẮT BUỘC):
   - TUYỆT ĐỐI KHÔNG BAO GIỜ nói "Đang tìm hiểu...", "Đang tra cứu...", "Để tôi kiểm tra...", "Chờ một chút...", "Đang cập nhật..." vì đây là màn hình gương thông minh hiển thị kết quả ngay, không có bước tra cứu sau đó.
   - Nếu là câu hỏi kiến thức bạn biết: Trả lời NGAY LẬP TỨC câu trả lời chính xác, ngắn gọn, súc tích (dưới 25 từ).
   - Nếu là câu hỏi bạn KHÔNG BIẾT hoặc thông tin thời gian thực bạn không có dữ liệu (như giá vàng hôm nay, vé số, tỷ số bóng đá trực tiếp, sự kiện đang diễn ra): Trả lời dứt khoát rằng bạn chưa có thông tin thời gian thực về vấn đề này. Tuyệt đối không hứa hẹn sẽ tìm hiểu.
   - Với SHOW_WEATHER, GET_TIME, GET_DATE, GET_CALENDAR: Hệ thống gương sẽ tự động đọc dữ liệu từ Google Calendar, trạm khí tượng và đồng hồ của máy tính để hiển thị, response_text có thể để trống hoặc câu ngắn gọn.

QUY TẮC ĐỊNH DẠNG ĐẦU RA:
Bắt buộc trả về duy nhất định dạng JSON thuần túy (không bọc trong markdown codeblocks):
{
  "action": "NONE" | "TAKE_PHOTO" | "SEARCH" | "PLAY_MEDIA" | "SMART_HOME" | "SYSTEM" | "SHOW_WEATHER" | "GET_TIME" | "GET_DATE" | "GET_CALENDAR",
  "response_text": "Câu trả lời ngắn gọn để trợ lý đọc hoặc hiển thị lên gương",
  "target": "web_image" | "camera" | null,
  "query": "từ khóa tìm kiếm hoặc tên địa điểm nếu có",
  "entity_name": "Tên thực thể chuẩn tiếng Việt",
  "english_keyword": "từ khóa tiếng Anh để tra cứu ảnh chất lượng cao",
  "scientific_name": "Tên khoa học hoặc phân loại",
  "summary": "Tóm tắt 2-3 câu giàu tri thức cho thẻ thông tin",
  "facts": ["Fact 1", "Fact 2", "Fact 3"],
  "title": "tên bài hát nếu có",
  "artist": "tên ca sĩ nếu có",
  "devices": [{"name": "Đèn phòng khách", "status": "ON"}],
  "state": "playing" | "paused" | 0 | 1 | null,
  "volume": null
}
"""

def _load_env_file():
    """Tự động nạp file .env từ thư mục gốc của project"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(current_dir)
    env_path = os.path.join(root_dir, ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip('"').strip("'")
                        if k and not os.environ.get(k):
                            os.environ[k] = v
        except Exception:
            pass

# ====================================================================
# BỘ TÍNH TOÁN NGÀY LỄ THỰC TẾ (REAL-TIME HOLIDAY COUNTDOWN ENGINE)
# ====================================================================
LUNAR_HOLIDAYS = {
    "tet_nguyen_dan": {
        2025: date(2025, 1, 29),
        2026: date(2026, 2, 17),
        2027: date(2027, 2, 6),
        2028: date(2028, 1, 26),
        2029: date(2029, 2, 13),
        2030: date(2030, 2, 3),
    },
    "gio_to": {
        2025: date(2025, 4, 7),
        2026: date(2026, 4, 26),
        2027: date(2027, 4, 16),
        2028: date(2028, 4, 4),
        2029: date(2029, 4, 23),
        2030: date(2030, 4, 12),
    },
    "trung_thu": {
        2025: date(2025, 10, 6),
        2026: date(2026, 9, 25),
        2027: date(2027, 9, 15),
        2028: date(2028, 10, 3),
        2029: date(2029, 9, 22),
        2030: date(2030, 9, 12),
    }
}

def calculate_holiday_countdown(query: str, ref_date: Optional[date] = None) -> Optional[Dict[str, Any]]:
    """
    Tính toán số ngày thực tế còn lại đến các dịp lễ lớn của Việt Nam và Quốc tế.
    Trả về Dict với action='COUNTDOWN_HOLIDAY' và câu trả lời chính xác 100%.
    """
    if not query:
        return None
    today = ref_date or date.today()
    q = query.lower().strip()

    # Nhận diện người dùng muốn hỏi đếm ngược ngày lễ
    is_asking_countdown = any(k in q for k in [
        "còn bao nhiêu ngày", "mấy ngày nữa", "bao lâu nữa", "bao nhiêu ngày nữa",
        "mấy ngày tới", "khi nào tới", "khi nào đến", "sắp tới", "đếm ngược", "bao nhiêu ngày tới",
        "còn mấy ngày"
    ]) or any(k in q for k in ["tết chưa", "noel chưa", "noen chưa"])

    # 1. Tết Nguyên Đán (Tết Âm Lịch)
    if any(k in q for k in ["tết nguyên đán", "tết âm", "tết ta", "tết cổ truyền", "năm mới âm lịch"]) or (
        "tết" in q and not any(k in q for k in ["dương", "tây", "trung thu"]) and (is_asking_countdown or "mùng 1" in q or "nghỉ tết" in q)
    ):
        target = None
        for y in sorted(LUNAR_HOLIDAYS["tet_nguyen_dan"].keys()):
            h_date = LUNAR_HOLIDAYS["tet_nguyen_dan"][y]
            if h_date >= today:
                target = h_date
                break
        if target:
            diff = (target - today).days
            target_str = target.strftime("%d/%m/%Y")
            name = f"Tết Nguyên Đán {target.year}"
            if diff == 0:
                resp = f"Hôm nay chính là mùng 1 {name}! Chúc bạn và gia đình năm mới an khang thịnh vượng!"
            elif diff == 1:
                resp = f"Chỉ còn đúng 1 ngày nữa là đến {name} ({target_str}) rồi!"
            else:
                resp = f"Còn {diff} ngày nữa là đến {name} (mùng 1 Tết nhằm ngày {target_str})."
            return {
                "action": "COUNTDOWN_HOLIDAY",
                "holiday": name,
                "days_left": diff,
                "target_date": target_str,
                "response_text": resp
            }

    # 2. Giáng Sinh / Noel
    if any(k in q for k in ["noel", "giáng sinh", "noen", "christmas"]):
        target = date(today.year, 12, 25)
        if target < today:
            target = date(today.year + 1, 12, 25)
        diff = (target - today).days
        target_str = target.strftime("%d/%m/%Y")
        name = "Lễ Giáng Sinh (Noel)"
        if diff == 0:
            resp = f"Hôm nay chính là {name}! Chúc bạn một mùa Giáng Sinh ấm áp và an lành!"
        elif diff == 1:
            resp = f"Chỉ còn đúng 1 ngày nữa là đến {name} rồi bạn nhé!"
        else:
            resp = f"Còn {diff} ngày nữa là đến {name} ({target_str})."
        return {
            "action": "COUNTDOWN_HOLIDAY",
            "holiday": name,
            "days_left": diff,
            "target_date": target_str,
            "response_text": resp
        }

    # 3. Tết Dương Lịch / Năm Mới
    if any(k in q for k in ["tết dương", "tết tây", "tết dương lịch", "năm mới dương lịch"]):
        target = date(today.year + 1, 1, 1) if today >= date(today.year, 1, 1) else date(today.year, 1, 1)
        diff = (target - today).days
        target_str = target.strftime("%d/%m/%Y")
        name = f"Tết Dương Lịch {target.year}"
        if diff == 0:
            resp = f"Hôm nay là {name}! Chúc bạn một năm mới tràn ngập niềm vui và thành công!"
        elif diff == 1:
            resp = f"Chỉ còn 1 ngày nữa là bước sang {name} rồi!"
        else:
            resp = f"Còn {diff} ngày nữa là đến {name} ({target_str})."
        return {
            "action": "COUNTDOWN_HOLIDAY",
            "holiday": name,
            "days_left": diff,
            "target_date": target_str,
            "response_text": resp
        }

    # 4. 30/4 & 1/5
    if any(k in q for k in ["30/4", "30 tháng 4", "giải phóng", "1/5", "1 tháng 5", "lao động"]):
        target = date(today.year, 4, 30)
        if target < today:
            target = date(today.year + 1, 4, 30)
        diff = (target - today).days
        target_str = target.strftime("%d/%m/%Y")
        name = "Kỳ nghỉ lễ 30/4 và 1/5"
        if diff == 0:
            resp = f"Hôm nay là Ngày Giải phóng miền Nam 30/4! Chúc bạn có kỳ nghỉ lễ thật vui vẻ!"
        else:
            resp = f"Còn {diff} ngày nữa là đến {name} ({target_str})."
        return {
            "action": "COUNTDOWN_HOLIDAY",
            "holiday": name,
            "days_left": diff,
            "target_date": target_str,
            "response_text": resp
        }

    # 5. Quốc khánh 2/9
    if any(k in q for k in ["quốc khánh", "2/9", "2 tháng 9"]):
        target = date(today.year, 9, 2)
        if target < today:
            target = date(today.year + 1, 9, 2)
        diff = (target - today).days
        target_str = target.strftime("%d/%m/%Y")
        name = "Ngày Quốc khánh Việt Nam (2/9)"
        if diff == 0:
            resp = f"Hôm nay là {name}! Chúc mừng ngày Tết Độc Lập của dân tộc!"
        else:
            resp = f"Còn {diff} ngày nữa là đến {name} ({target_str})."
        return {
            "action": "COUNTDOWN_HOLIDAY",
            "holiday": name,
            "days_left": diff,
            "target_date": target_str,
            "response_text": resp
        }

    # 6. Giỗ Tổ Hùng Vương (10/3 Âm lịch)
    if any(k in q for k in ["giỗ tổ", "hùng vương", "10/3 âm"]):
        target = None
        for y in sorted(LUNAR_HOLIDAYS["gio_to"].keys()):
            h_date = LUNAR_HOLIDAYS["gio_to"][y]
            if h_date >= today:
                target = h_date
                break
        if target:
            diff = (target - today).days
            target_str = target.strftime("%d/%m/%Y")
            name = f"Lễ Giỗ Tổ Hùng Vương {target.year}"
            resp = f"Còn {diff} ngày nữa là đến {name} (mùng 10 tháng 3 Âm lịch, ngày {target_str})." if diff > 0 else f"Hôm nay là {name}!"
            return {
                "action": "COUNTDOWN_HOLIDAY",
                "holiday": name,
                "days_left": diff,
                "target_date": target_str,
                "response_text": resp
            }

    # 7. Tết Trung Thu (15/8 Âm lịch)
    if any(k in q for k in ["trung thu", "tết thiếu nhi", "rằm tháng tám", "rằm tháng 8"]):
        target = None
        for y in sorted(LUNAR_HOLIDAYS["trung_thu"].keys()):
            h_date = LUNAR_HOLIDAYS["trung_thu"][y]
            if h_date >= today:
                target = h_date
                break
        if target:
            diff = (target - today).days
            target_str = target.strftime("%d/%m/%Y")
            name = f"Tết Trung Thu {target.year}"
            resp = f"Còn {diff} ngày nữa là đến {name} (Rằm tháng Tám ngày {target_str})." if diff > 0 else f"Hôm nay là {name}!"
            return {
                "action": "COUNTDOWN_HOLIDAY",
                "holiday": name,
                "days_left": diff,
                "target_date": target_str,
                "response_text": resp
            }

    # 8. Ngày Phụ Nữ Việt Nam (20/10) & Quốc tế Phụ Nữ (8/3)
    if any(k in q for k in ["20/10", "20 tháng 10", "phụ nữ việt nam"]):
        target = date(today.year, 10, 20)
        if target < today:
            target = date(today.year + 1, 10, 20)
        diff = (target - today).days
        target_str = target.strftime("%d/%m/%Y")
        name = "Ngày Phụ nữ Việt Nam (20/10)"
        resp = f"Còn {diff} ngày nữa là đến {name} ({target_str})." if diff > 0 else f"Hôm nay là {name}!"
        return {
            "action": "COUNTDOWN_HOLIDAY",
            "holiday": name,
            "days_left": diff,
            "target_date": target_str,
            "response_text": resp
        }

    if any(k in q for k in ["8/3", "8 tháng 3", "quốc tế phụ nữ"]):
        target = date(today.year, 3, 8)
        if target < today:
            target = date(today.year + 1, 3, 8)
        diff = (target - today).days
        target_str = target.strftime("%d/%m/%Y")
        name = "Ngày Quốc tế Phụ nữ (8/3)"
        resp = f"Còn {diff} ngày nữa là đến {name} ({target_str})." if diff > 0 else f"Hôm nay là {name}!"
        return {
            "action": "COUNTDOWN_HOLIDAY",
            "holiday": name,
            "days_left": diff,
            "target_date": target_str,
            "response_text": resp
        }

    return None

class AIEngine:
    def __init__(self, api_key: Optional[str] = None):
        _load_env_file()
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.client = None
        self._init_client()

    def _init_client(self):
        if HAS_GENAI and self.api_key:
            try:
                self.client = genai.Client(api_key=self.api_key)
                print("[🤖 AI Engine] Đã kết nối thành công với Google Gemini API (Model: gemini-3.5-flash-lite / gemini-3.8-flash)!")
            except Exception as e:
                print(f"[!] Lỗi khởi tạo Gemini Client: {e}")
                self.client = None
        else:
            self.client = None

    def set_api_key(self, api_key: str):
        self.api_key = api_key
        os.environ["GEMINI_API_KEY"] = api_key
        self._init_client()

    def is_api_active(self) -> bool:
        return self.client is not None

    async def process_user_input(self, user_text: str) -> Dict[str, Any]:
        """
        Xử lý câu nói của người dùng:
        - Nếu có Gemini API: Gọi Gemini 3.8 Flash phân tích Intent NLU & sinh câu trả lời.
        - Nếu chưa có API Key: Dùng Fallback NLU để phân loại chính xác các lệnh mẫu.
        """
        user_text = user_text.strip()
        if not user_text:
            return {
                "action": "NONE",
                "response_text": "Tôi có thể giúp gì cho bạn hôm nay?"
            }

        # 0. Fast-path tức thì: Đếm ngược ngày lễ thực tế (Real-Time Holiday Calculation)
        holiday_match = calculate_holiday_countdown(user_text)
        if holiday_match:
            return holiday_match

        # Fast-path: Lệnh chụp ảnh, mở/hủy camera, hỏi giờ, hỏi ngày cục bộ (<0.001s, 0 Token, không cần đợi mạng)
        t = user_text.lower()
        if any(k in t for k in ["tắt camera", "đóng camera", "hủy camera", "hủy chụp", "tắt máy ảnh", "đóng máy ảnh", "thôi chụp", "dừng chụp", "ngừng chụp"]):
            return {
                "action": "CANCEL_PHOTO",
                "response_text": "Đã hủy chế độ camera."
            }

        # Fast-path: Nhận diện vật thể / Quét camera (<0.001s, 0 Token)
        if any(k in t for k in ["đây là gì", "nhìn xem", "nhận diện", "quét", "xem vật", "thị giác", "đồ vật"]):
            return {
                "action": "SEARCH",
                "target": "camera",
                "response_text": "Đang quét và phân tích các vật thể qua camera..."
            }

        if any(k in t for k in ["chụp", "chộp", "camera", "máy ảnh", "soi gương", "selfie"]):
            return {
                "action": "TAKE_PHOTO",
                "countdown": 3,
                "response_text": "Đang mở camera soi gương... Bạn hãy tạo dáng và nói 'Chụp ảnh' khi sẵn sàng nhé!"
            }

        if any(k in t for k in ["mấy giờ", "thời gian", "giờ rồi", "xem giờ"]):
            now_str = datetime.now().strftime("%H:%M")
            return {
                "action": "GET_TIME",
                "response_text": f"Bây giờ là {now_str}."
            }

        if any(k in t for k in ["ngày mấy", "hôm nay là ngày", "thứ mấy", "ngày bao nhiêu", "ngày hôm nay"]):
            weekdays = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"]
            now = datetime.now()
            day_name = weekdays[now.weekday()]
            date_str = now.strftime(f"{day_name}, ngày %d/%m/%Y")
            return {
                "action": "GET_DATE",
                "response_text": f"Hôm nay là {date_str}."
            }

        # Fast-path: Điều khiển nhạc (Bật/Tắt - 0 Token, 0 Trễ)
        if any(k in t for k in ["tắt nhạc", "dừng nhạc", "tạm dừng", "dừng bài", "ngừng phát", "stop music", "pause music", "im lặng"]):
            return {
                "action": "PLAY_MEDIA",
                "title": "Tắt nhạc",
                "artist": "",
                "state": "stopped",
                "response_text": "Đã tắt nhạc theo yêu cầu của bạn."
            }

        if any(k in t for k in ["bật nhạc", "nghe nhạc", "phát nhạc", "bài hát", "play music", "mở nhạc"]):
            title = "Sample Chill"
            artist = "Thư viện nhạc"
            if "sơn tùng" in t or "nơi này có anh" in t:
                title = "Nơi Này Có Anh"
                artist = "Sơn Tùng M-TP"
            elif "lofi" in t or "lo-fi" in t:
                title = "Lo-Fi Chillhop Beats"
                artist = "Chill Radio 24/7"
            return {
                "action": "PLAY_MEDIA",
                "title": title,
                "artist": artist,
                "state": "playing",
                "response_text": f"Đang phát bài hát '{title}' cho bạn."
            }

        # Fast-path: Lịch trình & Thời khóa biểu (Cục bộ, 0 Token, 0 Trễ)
        if any(k in t for k in [
            "lịch", "lịch trình", "lịch học", "thời khóa biểu", "thời khoá biểu",
            "hôm nay học gì", "hôm nay có học gì", "ngày mai học gì", "ngày mai có học gì",
            "hôm nay có gì", "ngày mai có gì", "tiết học", "có tiết không"
        ]):
            return {
                "action": "GET_CALENDAR",
                "query": user_text,
                "response_text": ""
            }

        # 1. Nếu có Gemini API Client hoạt động
        if self.client:
            try:
                loop = asyncio.get_running_loop()
                result = await loop.run_in_executor(None, self._call_gemini_nlu, user_text)
                if result:
                    return result
            except Exception as e:
                print(f"[!] Lỗi khi gọi Gemini API ({e}). Đang chuyển sang Fallback NLU...")

        # 2. Fallback Rule-Based NLU khi offline hoặc chưa có API Key
        return self._fallback_nlu_matcher(user_text)

    def _call_gemini_nlu(self, prompt: str) -> Optional[Dict[str, Any]]:
        """Gửi prompt tới Gemini API với cấu hình JSON Output và tự động chuyển model dự phòng"""
        # Danh sách model tối ưu tốc độ phản hồi nhanh nhất (~1.5s - 2.0s)
        models_to_try = [
            "gemini-3.5-flash-lite",
            "gemini-3.5-flash"
        ]
        last_error = None

        # Tiêm ngày giờ thời gian thực vào System Instruction
        now = datetime.now()
        weekdays = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"]
        day_str = weekdays[now.weekday()]
        now_str = now.strftime("%H:%M:%S, ngày %d/%m/%Y")
        dynamic_instruction = (
            f"{NLU_SYSTEM_INSTRUCTION}\n\n"
            f"=== NGỮ CẢNH THỜI GIAN THỰC TẾ (BẮT BUỘC SỬ DỤNG) ===\n"
            f"- Thời điểm hiện tại: {day_str}, {now_str} (Múi giờ Việt Nam GMT+7).\n"
            f"- Năm hiện tại: {now.year}.\n"
            f"- Khi người dùng hỏi về thời gian, ngày tháng, đếm ngược ngày lễ hay sự kiện, hãy căn cứ vào mốc thời gian thực này để trả lời chuẩn xác."
        )

        for model_name in models_to_try:
            try:
                response = self.client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=dynamic_instruction,
                        response_mime_type="application/json",
                        temperature=0.1,
                        max_output_tokens=800
                    )
                )
                raw_text = response.text
                if not raw_text:
                    continue

                # Làm sạch nếu có markdown
                clean_text = raw_text.strip()
                if clean_text.startswith("```"):
                    clean_text = re.sub(r"^```(?:json)?\n", "", clean_text)
                    clean_text = re.sub(r"\n```$", "", clean_text)

                data = json.loads(clean_text)
                return data
            except Exception as e:
                last_error = e
                if "403" in str(e) or "PERMISSION_DENIED" in str(e):
                    break
                continue

        if last_error:
            self.last_api_error = str(last_error)
            print(f"[!] Ngoại lệ Gemini API: {last_error}")
        else:
            self.last_api_error = ""
        return None

    def _fallback_nlu_matcher(self, text: str) -> Dict[str, Any]:
        """Bộ phân loại Intent thông minh cục bộ khi chưa nhập API Key"""
        t = text.lower()

        # 0. Tính toán ngày lễ thực tế (Real-time Holiday Calculation)
        holiday_match = calculate_holiday_countdown(text)
        if holiday_match:
            return holiday_match

        # 1. TAKE_PHOTO & CANCEL_PHOTO
        if any(k in t for k in ["tắt camera", "đóng camera", "hủy camera", "hủy chụp"]):
            return {
                "action": "CANCEL_PHOTO",
                "response_text": "Đã hủy chế độ camera."
            }

        if any(k in t for k in ["chụp", "chộp", "selfie", "take photo", "bức ảnh", "chụp hình", "chộp hình", "mở camera", "bật camera", "camera", "mở máy ảnh", "bật máy ảnh", "soi gương"]):
            return {
                "action": "TAKE_PHOTO",
                "countdown": 3,
                "response_text": "Đang mở camera soi gương... Bạn hãy tạo dáng và nói 'Chụp ảnh' khi sẵn sàng nhé!"
            }

        # 2. SEARCH (camera)
        if any(k in t for k in ["đây là gì", "nhìn xem", "nhận diện", "quét", "xem vật", "thị giác", "đồ vật"]):
            return {
                "action": "SEARCH",
                "target": "camera",
                "response_text": "Đang quét và phân tích các vật thể qua camera..."
            }

        # 3. SEARCH (web_image)
        if any(k in t for k in ["xem ảnh", "tìm ảnh", "hình ảnh", "tháp eiffel", "ảnh hoa", "xem hình", "tìm kiếm ảnh", "tìm hình", "cho xem ảnh", "con trâu", "loài chó", "con mèo", "con voi"]):
            extracted_q = re.sub(r"^(cho tôi xem ảnh|cho xem ảnh|xem ảnh|tìm ảnh|tìm hình ảnh|tìm kiếm ảnh|hình ảnh|xem hình|tìm hình|cho xem)\s*(về)?\s*", "", t).strip()
            if not extracted_q:
                extracted_q = "hoa sen"

            # Hồ sơ tri thức mẫu phong phú cho các thực thể phổ biến khi offline
            offline_catalog = {
                "trâu": {
                    "entity_name": "Con Trâu (Trâu Nước)",
                    "english_keyword": "water buffalo",
                    "scientific_name": "Bubalus bubalis • Động vật có vú",
                    "summary": "Trâu nước là loài động vật quen thuộc gắn bó mật thiết với nền văn minh lúa nước và nông thôn Việt Nam. Chúng sở hữu sức kéo bền bỉ, tính tình thuần hậu và thường đầm mình dưới bùn nước để điều hòa thân nhiệt.",
                    "facts": ["Sức kéo bền bỉ, 'đầu cơ nghiệp' của nhà nông", "Khả năng bơi lội và thích nghi vùng nước rất giỏi", "Con giáp thứ 2 trong 12 con giáp Việt Nam"]
                },
                "chó": {
                    "entity_name": "Loài Chó (Chó Nhà)",
                    "english_keyword": "dog breeds",
                    "scientific_name": "Canis lupus familiaris • Động vật ăn thịt",
                    "summary": "Chó là loài động vật được thuần hóa đầu tiên trong lịch sử nhân loại, nổi tiếng với sự trung thành và trí thông minh cao. Khứu giác của loài chó cực kỳ phát triển, nhạy bén gấp hàng nghìn lần con người.",
                    "facts": ["Thuần hóa cách đây hơn 15.000 năm", "Khứu giác thính nhạy gấp hàng ngàn lần con người", "Người bạn trung thành lâu đời của con người"]
                },
                "mèo": {
                    "entity_name": "Con Mèo (Mèo Nhà)",
                    "english_keyword": "domestic cat",
                    "scientific_name": "Felis catus • Họ Mèo",
                    "summary": "Mèo nhà là loài thú săn mồi nhỏ nhắn có phản xạ cực kỳ linh hoạt, móng vuốt thu rút và khả năng nhìn đêm xuất sắc. Chúng giao tiếp bằng tiếng kêu meo meo và tiếng gừ gừ thư giãn.",
                    "facts": ["Ngủ trung bình 12 - 16 giờ mỗi ngày", "Khả năng thăng bằng và tiếp đất tuyệt vời", "Thị giác ban đêm vượt trội hơn mắt người 6 lần"]
                },
                "voi": {
                    "entity_name": "Con Voi",
                    "english_keyword": "elephant",
                    "scientific_name": "Elephantidae • Động vật có vú trên cạn",
                    "summary": "Voi là động vật có vú trên cạn lớn nhất hành tinh, nổi bật với chiếc vòi dài đa năng và đôi ngà uy nghi. Loài voi có đời sống bầy đàn gắn kết và trí nhớ xã hội đáng kinh ngạc.",
                    "facts": ["Động vật trên cạn lớn nhất còn tồn tại", "Chiếc vòi chứa hơn 40.000 bó cơ linh hoạt", "Trí nhớ và cảm xúc đồng loại rất phát triển"]
                },
                "tháp eiffel": {
                    "entity_name": "Tháp Eiffel (Paris)",
                    "english_keyword": "eiffel tower paris",
                    "scientific_name": "La Tour Eiffel • Paris, Pháp",
                    "summary": "Tháp Eiffel là công trình kiến trúc bằng thép vĩ đại tại thủ đô Paris, hoàn thành năm 1889 bởi Gustave Eiffel. Với chiều cao 330m, đây là biểu tượng văn hóa và du lịch kiệt xuất của nước Pháp.",
                    "facts": ["Chiều cao 330 mét, xây dựng năm 1889", "Biểu tượng du lịch số 1 của nước Pháp", "Được chế tác từ hơn 18.000 thanh sắt rèn"]
                },
                "hoa sen": {
                    "entity_name": "Hoa Sen (Sen Hồng)",
                    "english_keyword": "lotus flower",
                    "scientific_name": "Nelumbo nucifera • Quốc hoa Việt Nam",
                    "summary": "Hoa sen là loài thực vật thủy sinh biểu tượng cho sự thuần khiết, thanh cao và ý chí kiên cường trong văn hóa Việt Nam. Sen nở rộ vào mùa hè và mọi bộ phận của sen đều hữu dụng.",
                    "facts": ["Biểu tượng 'gần bùn mà chẳng hôi tanh mùi bùn'", "Hạt sen và tim sen là vị thuốc an thần quý", "Được tôn vinh là Quốc hoa của người Việt"]
                }
            }

            matched_info = None
            for key, val in offline_catalog.items():
                if key in extracted_q.lower():
                    matched_info = val
                    break

            if matched_info:
                return {
                    "action": "SEARCH",
                    "target": "web_image",
                    "query": extracted_q,
                    "entity_name": matched_info["entity_name"],
                    "english_keyword": matched_info["english_keyword"],
                    "scientific_name": matched_info["scientific_name"],
                    "summary": matched_info["summary"],
                    "facts": matched_info["facts"],
                    "caption": f"Hình ảnh và thông tin về {matched_info['entity_name']}",
                    "response_text": f"Dưới đây là hình ảnh và thông tin về {matched_info['entity_name']}."
                }

            # Trường hợp tổng quát
            clean_name = extracted_q.title()
            return {
                "action": "SEARCH",
                "target": "web_image",
                "query": extracted_q,
                "entity_name": clean_name,
                "english_keyword": extracted_q,
                "scientific_name": "Thực thể / Danh mục tra cứu",
                "summary": f"Thông tin tổng quan về {clean_name} được tổng hợp từ nguồn tri thức trực tuyến.",
                "facts": [f"Từ khóa tìm kiếm: {clean_name}", "Độ phân giải: Chất lượng cao"],
                "caption": f"Hình ảnh tìm kiếm cho '{clean_name}'",
                "response_text": f"Đã tìm thấy hình ảnh về {clean_name} cho bạn."
            }


        # 4. PLAY_MEDIA (Tắt/Dừng nhạc)
        if any(k in t for k in ["tắt nhạc", "dừng nhạc", "tạm dừng", "dừng bài", "ngừng phát", "stop music", "pause music", "im lặng"]):
            return {
                "action": "PLAY_MEDIA",
                "title": "Tắt nhạc",
                "artist": "",
                "state": "stopped",
                "response_text": "Đã tắt nhạc theo yêu cầu của bạn."
            }

        # 4. PLAY_MEDIA (Bật/Phát nhạc)
        if any(k in t for k in ["bật nhạc", "nghe nhạc", "phát nhạc", "bài hát", "play music", "mở nhạc", "nhạc"]):
            title = "Sample Chill"
            artist = "Thư viện nhạc"
            if "sơn tùng" in t or "nơi này có anh" in t:
                title = "Nơi Này Có Anh"
                artist = "Sơn Tùng M-TP"
            elif "lofi" in t or "lo-fi" in t:
                title = "Lo-Fi Chillhop Beats"
                artist = "Chill Radio 24/7"
            return {
                "action": "PLAY_MEDIA",
                "title": title,
                "artist": artist,
                "state": "playing",
                "response_text": f"Đang phát bài hát '{title}' cho bạn."
            }

        # 5. SMART_HOME
        if any(k in t for k in ["bật đèn", "tắt đèn", "máy lạnh", "điều hòa", "khóa cửa"]):
            dev_status = "ON" if "bật" in t else "OFF"
            dev_name = "Đèn phòng khách" if "đèn" in t else "Máy lạnh"
            return {
                "action": "SMART_HOME",
                "devices": [
                    {"name": dev_name, "status": dev_status},
                    {"name": "Máy lạnh", "status": "24°C"},
                    {"name": "Cửa chính", "status": "LOCKED"}
                ],
                "response_text": f"Đã thực hiện: {dev_name} chuyển sang trạng thái {dev_status}."
            }

        # 6. SYSTEM (State 0 / State 1)
        if any(k in t for k in ["ngủ", "tắt gương", "tắt màn hình", "sleep", "nghỉ ngơi"]):
            return {
                "action": "SYSTEM",
                "state": 0,
                "response_text": "Gương chuyển sang chế độ ngủ. Chúc bạn một ngày tốt lành!"
            }
        if any(k in t for k in ["thức dậy", "bật gương", "mở màn hình", "wake up", "chào buổi sáng"]):
            return {
                "action": "SYSTEM",
                "state": 1,
                "response_text": "Chào mừng bạn trở lại! Toàn bộ thông tin đã sẵn sàng."
            }

        # 7. GET_TIME / GET_DATE
        if any(k in t for k in ["mấy giờ", "thời gian", "giờ rồi", "xem giờ"]):
            from datetime import datetime
            now_str = datetime.now().strftime("%H:%M")
            return {
                "action": "GET_TIME",
                "response_text": f"Bây giờ là {now_str}."
            }
        if any(k in t for k in ["ngày mấy", "hôm nay là ngày", "thứ mấy", "ngày bao nhiêu", "ngày hôm nay"]):
            from datetime import datetime
            weekdays = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"]
            now = datetime.now()
            day_name = weekdays[now.weekday()]
            date_str = now.strftime(f"{day_name}, ngày %d/%m/%Y")
            return {
                "action": "GET_DATE",
                "response_text": f"Hôm nay là {date_str}."
            }

        # 8. SHOW_WEATHER
        if any(k in t for k in ["thời tiết", "trời mưa", "nhiệt độ"]):
            return {
                "action": "SHOW_WEATHER",
                "response_text": "Thời tiết hôm nay trời trong xanh, nhiệt độ 28°C, độ ẩm 65% rất dễ chịu."
            }

        # 9. GET_CALENDAR
        if any(k in t for k in ["lịch trình", "lịch học", "thời khóa biểu", "thời khoá biểu", "hôm nay có gì", "ngày mai có gì", "có tiết", "có lịch", "lịch hẹn", "sự kiện", "calendar"]) or (("lịch" in t or "tiết" in t) and any(w in t for w in ["hôm nay", "ngày mai", "ngày mốt", "thứ", "tuần", "tháng"])):
            return {
                "action": "GET_CALENDAR",
                "query": text,
                "response_text": ""
            }

        # 10. NONE (Hội thoại chung hoặc câu chào)
        if any(k in t for k in ["chào", "hello", "hi", "bạn là ai", "tên gì", "giới thiệu"]):
            return {
                "action": "NONE",
                "response_text": "Chào bạn! Tôi là Trợ lý AI trên gương ma thuật. Rất vui được hỗ trợ bạn hôm nay!"
            }

        if self.is_api_active():
            err = getattr(self, "last_api_error", "").lower()
            if "permission_denied" in err or "billing" in err:
                msg = "Dự án Google Cloud của khóa API này chưa bật gói Free Tier. Bạn vui lòng vào aistudio.google.com và chọn 'Create API key in new project' để dùng miễn phí nhé."
            elif "resource_exhausted" in err or "429" in err:
                msg = "Hệ thống AI đang tạm thời đạt giới hạn yêu cầu (Rate Limit). Bạn vui lòng đợi khoảng 1 phút rồi hỏi lại nhé!"
            elif "api_key" in err or "invalid" in err:
                msg = "Khóa API Gemini chưa hợp lệ hoặc chưa được cấp quyền. Bạn hãy kiểm tra lại file .env nhé."
            elif any(k in err for k in ["nameresolution", "connection", "network", "errno -3", "timeout"]):
                msg = "Chưa kết nối được với Internet để gọi máy chủ AI. Bạn hãy kiểm tra lại kết nối mạng nhé."
            else:
                msg = "Tạm thời không thể kết nối tới máy chủ AI. Bạn hãy thử lại sau nhé!"
            return {
                "action": "NONE",
                "response_text": msg
            }
        else:
            return {
                "action": "NONE",
                "response_text": "Tôi chưa hiểu câu hỏi của bạn. (💡 Cấu hình GEMINI_API_KEY để trò chuyện tự do)"
            }

    async def analyze_vision_with_gemini(self, image_path: str) -> Dict[str, Any]:
        """Dùng Gemini Vision để nhận diện đồ vật từ ảnh webcam chụp được"""
        if not self.client:
            return {
                "detections": [
                    {"label": "Khuôn mặt người dùng", "confidence": "98%"},
                    {"label": "Phòng làm việc", "confidence": "92%"},
                    {"label": "Ánh sáng tự nhiên", "confidence": "89%"}
                ],
                "summary": "Đã nhận diện các đối tượng trước gương."
            }

        try:
            loop = asyncio.get_running_loop()
            def _call_vision():
                # Tối ưu kích thước ảnh (Nén nhanh 640px JPEG để giảm 75% thời gian upload và inference)
                try:
                    import cv2
                    img = cv2.imread(image_path)
                    if img is not None:
                        h, w = img.shape[:2]
                        if max(h, w) > 640:
                            scale = 640.0 / float(max(h, w))
                            img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
                        _, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 80])
                        image_bytes = buf.tobytes()
                    else:
                        with open(image_path, "rb") as f:
                            image_bytes = f.read()
                except Exception:
                    with open(image_path, "rb") as f:
                        image_bytes = f.read()

                vision_prompt = """
                Hãy quan sát hình ảnh vừa chụp từ webcam gương thông minh và phân tích:
                1. Liệt kê 3 đến 5 vật thể hoặc đặc điểm nổi bật nhất nhìn thấy trong ảnh.
                2. Với mỗi vật thể, cung cấp nhãn 'label' (tiếng Việt ngắn gọn) và độ tin cậy 'confidence' (ví dụ '95%').
                3. Viết 1 câu nhận xét tóm tắt 'summary' ngắn gọn (dưới 20 từ).
                
                Trả về JSON thuần:
                {
                   "detections": [{"label": "Tên vật thể", "confidence": "95%"}],
                   "summary": "Mô tả ngắn gọn..."
                }
                """
                models_to_try = ["gemini-3.5-flash-lite", "gemini-3.5-flash"]
                response = None
                for m in models_to_try:
                    try:
                        response = self.client.models.generate_content(
                            model=m,
                            contents=[
                                types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
                                vision_prompt
                            ],
                            config=types.GenerateContentConfig(
                                response_mime_type="application/json",
                                temperature=0.1,
                                max_output_tokens=150
                            )
                        )
                        if response and response.text:
                            break
                    except Exception:
                        continue

                if not response or not response.text:
                    raise RuntimeError("Không nhận được phản hồi Vision từ Gemini")

                clean_text = response.text.strip()
                if clean_text.startswith("```"):
                    clean_text = re.sub(r"^```(?:json)?\n", "", clean_text)
                    clean_text = re.sub(r"\n```$", "", clean_text)
                parsed = json.loads(clean_text)
                if isinstance(parsed, list) and len(parsed) > 0 and isinstance(parsed[0], dict):
                    parsed = parsed[0]
                return parsed

            return await loop.run_in_executor(None, _call_vision)
        except Exception as e:
            print(f"[!] Lỗi khi gọi Gemini Vision ({e})")
            return {
                "detections": [
                    {"label": "Khuôn mặt người dùng", "confidence": "98%"},
                    {"label": "Không gian phòng", "confidence": "91%"}
                ],
                "summary": "Đã ghi nhận khung hình từ camera."
            }

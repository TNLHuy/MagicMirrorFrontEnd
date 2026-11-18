"""
====================================================================
  CALENDAR SERVICE (GOOGLE CALENDAR ICAL PARSER & SCHEDULER)
  Đồng bộ lịch học & sự kiện từ Google Calendar của người dùng (iCal)
  - Hỗ trợ sự kiện lặp lại hàng tuần (RRULE: FREQ=WEEKLY, INTERVAL=1/2)
  - Nhận diện ngày hỏi: "hôm nay", "ngày mai", "thứ năm", "thứ sáu", "ngày 10/10"
  - Tự động sinh câu thoại tự nhiên cho Trợ lý AI và danh sách sự kiện cho Widget
====================================================================
"""

import hashlib
import json
import os
import re
import time
import datetime
import urllib.request
from typing import List, Dict, Optional, Tuple

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CALENDARS_JSON_PATH = os.path.join(PROJECT_ROOT, "data", "calendars.json")
CACHE_DIR = os.path.join(os.path.dirname(__file__), "calendar_cache")
os.makedirs(CACHE_DIR, exist_ok=True)
CACHE_TTL_SECONDS = 900  # 15 phút tự làm mới 1 lần

WEEKDAY_NAMES_VI = [
    "Thứ hai", "Thứ ba", "Thứ tư", "Thứ năm", "Thứ sáu", "Thứ bảy", "Chủ nhật"
]


class CalendarService:
    def __init__(self, ical_url: Optional[str] = None):
        self.default_ical_url = ical_url
        self.last_fetch_time = 0
        self.last_json_mtime = 0
        self.events_cache = []
        self._load_or_fetch()

    def get_active_calendars(self) -> List[Dict]:
        """Lấy danh sách các lịch đang kích hoạt từ data/calendars.json do người dùng cài trên Web Hub"""
        calendars = []
        if os.path.exists(CALENDARS_JSON_PATH):
            try:
                with open(CALENDARS_JSON_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        for item in data:
                            if item.get("enabled", True) and item.get("url") and item.get("url").strip():
                                calendars.append({
                                    "name": item.get("name", "Lịch cá nhân"),
                                    "url": item.get("url").strip(),
                                    "color": item.get("color", "#10b981")
                                })
            except Exception as e:
                print(f"[CalendarService] Lỗi đọc calendars.json: {e}")

        if not calendars:
            if self.default_ical_url:
                calendars.append({
                    "name": "Lịch mặc định",
                    "url": self.default_ical_url,
                    "color": "#10b981"
                })
            else:
                calendars.append({
                    "name": "Ngày lễ Việt Nam",
                    "url": "https://calendar.google.com/calendar/ical/vi.vietnamese%23holiday%40group.v.calendar.google.com/public/basic.ics",
                    "color": "#10b981"
                })
        return calendars

    def _fetch_single_ical(self, url: str) -> str:
        """Tải file .ics từ URL Google Calendar có cache cục bộ"""
        cache_key = hashlib.md5(url.encode("utf-8")).hexdigest()
        cache_file = os.path.join(CACHE_DIR, f"cal_{cache_key}.ics")

        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "MagicMirror-CalendarService/1.0"}
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = resp.read().decode("utf-8", errors="ignore")
                try:
                    with open(cache_file, "w", encoding="utf-8") as f:
                        f.write(data)
                except Exception:
                    pass
                return data
        except Exception as e:
            print(f"[CalendarService] Không thể tải iCal online từ {url} ({e}), dùng cache cục bộ.")
            if os.path.exists(cache_file):
                try:
                    with open(cache_file, "r", encoding="utf-8") as f:
                        return f.read()
                except Exception:
                    pass
            return ""

    def _load_or_fetch(self, force: bool = False):
        now = time.time()
        json_mtime = os.path.getmtime(CALENDARS_JSON_PATH) if os.path.exists(CALENDARS_JSON_PATH) else 0
        json_changed = json_mtime > self.last_json_mtime

        if force or json_changed or not self.events_cache or (now - self.last_fetch_time > CACHE_TTL_SECONDS):
            active_cals = self.get_active_calendars()
            all_events = []
            for cal in active_cals:
                content = self._fetch_single_ical(cal["url"])
                if content:
                    parsed = self._parse_all_events(content)
                    for ev in parsed:
                        ev["_calendar_name"] = cal["name"]
                        ev["_calendar_color"] = cal["color"]
                    all_events.extend(parsed)
            self.events_cache = all_events
            self.last_fetch_time = now
            self.last_json_mtime = json_mtime

    def _parse_all_events(self, ical_text: str) -> List[Dict]:
        """Phân tích cú pháp thô toàn bộ VEVENT trong file iCal (hỗ trợ line unfolding theo RFC 5545)"""
        # Unfold lines: các dòng bắt đầu bằng space hoặc tab nối tiếp vào dòng trước đó
        unfolded_lines = []
        for raw_line in ical_text.splitlines():
            if (raw_line.startswith(" ") or raw_line.startswith("\t")) and unfolded_lines:
                unfolded_lines[-1] += raw_line[1:]
            else:
                unfolded_lines.append(raw_line)

        events = []
        cur = None
        for line in unfolded_lines:
            line = line.strip()
            if line.startswith("BEGIN:VEVENT"):
                cur = {}
            elif line.startswith("END:VEVENT"):
                if cur:
                    events.append(cur)
                cur = None
            elif cur is not None and ":" in line:
                k, v = line.split(":", 1)
                prop = k.split(";")[0].strip().upper()
                cur[prop] = v.strip()
        return events

    @staticmethod
    def _parse_dt(dt_str: str) -> Optional[datetime.datetime]:
        """Chuyển đổi chuỗi ngày giờ 20261001T073000 hoặc 20261001 thành datetime"""
        if not dt_str:
            return None
        dt_str = dt_str.replace("Z", "")
        try:
            if "T" in dt_str:
                return datetime.datetime.strptime(dt_str[:15], "%Y%m%dT%H%M%S")
            else:
                d = datetime.datetime.strptime(dt_str[:8], "%Y%m%d")
                return d
        except Exception:
            return None

    def _event_matches_date(self, event: Dict, target_date: datetime.date) -> Tuple[bool, Optional[str]]:
        """
        Kiểm tra xem một sự kiện có diễn ra vào target_date hay không (kể cả lặp lại RRULE).
        Trả về (is_matched, note_text).
        Ví dụ note_text = 'Cách tuần' nếu là lớp thực hành lặp INTERVAL=2.
        """
        start_dt = self._parse_dt(event.get("DTSTART", ""))
        if not start_dt:
            return False, None

        start_date = start_dt.date()
        end_dt = self._parse_dt(event.get("DTEND", ""))
        end_date = end_dt.date() if end_dt else start_date
        rrule = event.get("RRULE", "")

        # 1. Sự kiện đơn lẻ (không có lặp lại)
        if not rrule:
            is_match = (start_date <= target_date <= end_date)
            return is_match, None

        # 2. Sự kiện lặp lại (RRULE)
        if target_date < start_date:
            return False, None

        # Phân tích các thuộc tính trong RRULE
        parts = {}
        for item in rrule.split(";"):
            if "=" in item:
                k, v = item.split("=", 1)
                parts[k.strip().upper()] = v.strip()

        # Kiểm tra ngày kết thúc của chu kỳ lặp (UNTIL)
        if "UNTIL" in parts:
            until_dt = self._parse_dt(parts["UNTIL"])
            if until_dt and target_date > until_dt.date():
                return False, None

        freq = parts.get("FREQ", "").upper()
        interval = int(parts.get("INTERVAL", 1))

        if freq == "WEEKLY":
            byday_map = {
                "MO": 0, "TU": 1, "WE": 2, "TH": 3, "FR": 4, "SA": 5, "SU": 6
            }
            if "BYDAY" in parts:
                bydays = [byday_map[d.strip()[-2:]] for d in parts["BYDAY"].split(",") if d.strip()[-2:] in byday_map]
                if target_date.weekday() not in bydays:
                    return False, None
            else:
                if target_date.weekday() != start_date.weekday():
                    return False, None

            # Xử lý INTERVAL tuần (ví dụ INTERVAL=2: lớp học cách 2 tuần)
            if interval > 1:
                delta_weeks = (target_date - start_date).days // 7
                if (delta_weeks % interval) == 0:
                    return True, None
                else:
                    # Thuộc thời khóa biểu ngày này nhưng là tuần cách phiên
                    return True, "Cách tuần"

            return True, None

        elif freq == "MONTHLY":
            if "BYMONTHDAY" in parts:
                bmd = int(parts["BYMONTHDAY"])
                return (target_date.day == bmd), None
            return (target_date.day == start_date.day), None

        elif freq == "DAILY":
            delta_days = (target_date - start_date).days
            return ((delta_days % interval) == 0), None

        return (start_date == target_date), None

    def get_events_for_date(self, target_date: datetime.date) -> List[Dict]:
        """Lấy danh sách tất cả sự kiện/môn học trong ngày target_date đã sắp xếp theo thứ tự thời gian trong ngày"""
        self._load_or_fetch()
        matched = []

        for e in self.events_cache:
            is_match, note = self._event_matches_date(e, target_date)
            if is_match:
                start_dt = self._parse_dt(e.get("DTSTART", ""))
                end_dt = self._parse_dt(e.get("DTEND", ""))

                summary = e.get("SUMMARY", "Lịch trình").strip()
                # Tách tên môn và mã môn (ví dụ: "Thiết kế hệ thống nhúng (CE224.R14)")
                clean_title = summary
                code = ""
                m = re.search(r"^(.*?)\s*\(([^)]+)\)$", summary)
                if m:
                    clean_title = m.group(1).strip()
                    code = m.group(2).strip()

                start_str = start_dt.strftime("%H:%M") if start_dt else ""
                end_str = end_dt.strftime("%H:%M") if end_dt else ""
                time_range = f"{start_str} - {end_str}" if (start_str and end_str) else (start_str or "Cả ngày")

                location = e.get("LOCATION", "").strip()

                matched.append({
                    "raw_summary": summary,
                    "title": clean_title,
                    "code": code,
                    "location": location,
                    "time": time_range,
                    "start_time": start_str,
                    "end_time": end_str,
                    "note": note or "",
                    "start_dt": start_dt or datetime.datetime.min
                })

        # Sắp xếp chính xác theo giờ bắt đầu trong ngày (sáng trước, chiều sau)
        matched.sort(key=lambda x: (x.get("start_time") or "00:00", x.get("end_time") or "00:00"))
        return matched

    @staticmethod
    def parse_target_date(user_text: str, base_date: Optional[datetime.date] = None) -> Tuple[datetime.date, str]:
        """
        Nhận diện ngày cần tra cứu từ câu nói tiếng Việt của người dùng.
        Trả về (target_date, date_label_short)
        """
        if base_date is None:
            base_date = datetime.date.today()

        t = (user_text or "").lower()

        # 1. Hôm nay
        if any(w in t for w in ["hôm nay", "bữa nay", "hôm ni", "ngày nay"]):
            return base_date, "Hôm nay"

        # 2. Ngày mai
        if any(w in t for w in ["ngày mai", "ngày mai có", "hôm sau", "mai"]):
            target = base_date + datetime.timedelta(days=1)
            return target, "Ngày mai"

        # 3. Ngày mốt / ngày kia
        if any(w in t for w in ["ngày mốt", "mốt", "ngày kia"]):
            target = base_date + datetime.timedelta(days=2)
            return target, "Ngày mốt"

        # 4. Các thứ trong tuần: "thứ hai" -> "thứ bảy", "chủ nhật"
        weekday_map = {
            "thứ hai": 0, "thứ 2": 0,
            "thứ ba": 1, "thứ 3": 1,
            "thứ tư": 2, "thứ 4": 2,
            "thứ năm": 3, "thứ 5": 3,
            "thứ sáu": 4, "thứ 6": 4,
            "thứ bảy": 5, "thứ 7": 5,
            "chủ nhật": 6, "chúa nhật": 6, "cn": 6
        }

        for kw, target_wd in weekday_map.items():
            if kw in t:
                # Tìm ngày gần nhất trong tuần tương ứng (tính từ hôm nay)
                cur_wd = base_date.weekday()
                diff = (target_wd - cur_wd) % 7
                if diff == 0 and ("tuần sau" in t or "tới" in t):
                    diff = 7
                target = base_date + datetime.timedelta(days=diff)
                label = WEEKDAY_NAMES_VI[target_wd]
                return target, label

        # 5. Cụ thể ngày X tháng Y (ví dụ "ngày 9 tháng 10", "ngày 10/10")
        m1 = re.search(r"ngày\s+(\d{1,2})\s*(?:tháng|\/)\s*(\d{1,2})", t)
        if m1:
            try:
                day = int(m1.group(1))
                month = int(m1.group(2))
                target = datetime.date(base_date.year, month, day)
                return target, f"Ngày {day:02d}/{month:02d}"
            except Exception:
                pass

        # 6. Chỉ có "ngày X"
        m2 = re.search(r"ngày\s+(\d{1,2})", t)
        if m2:
            try:
                day = int(m2.group(1))
                target = datetime.date(base_date.year, base_date.month, day)
                return target, f"Ngày {day:02d}/{base_date.month:02d}"
            except Exception:
                pass

        # Mặc định là Hôm nay
        return base_date, "Hôm nay"

    def get_schedule_payload(self, user_text: str, base_date: Optional[datetime.date] = None) -> Dict:
        """
        Tạo payload hoàn chỉnh gửi qua WebSocket cho giao diện gương MagicMirror
        """
        self._load_or_fetch()
        target_date, rel_label = self.parse_target_date(user_text, base_date)
        events = self.get_events_for_date(target_date)

        weekday_name = WEEKDAY_NAMES_VI[target_date.weekday()]
        formatted_date = target_date.strftime("%d/%m")
        date_full_label = f"{rel_label} • {weekday_name} ({formatted_date})"

        # Tạo câu thoại tự nhiên cho Trợ lý AI (đọc đầy đủ tất cả các sự kiện)
        prefix_time = f"{rel_label} {weekday_name.lower()}" if rel_label in ["Hôm nay", "Ngày mai", "Ngày mốt"] else f"Vào {rel_label.lower()}"
        if not events:
            if rel_label == "Hôm nay":
                speech = f"Hôm nay {weekday_name.lower()}, bạn không có lịch học nào. Bạn có thể tự do nghỉ ngơi!"
            else:
                speech = f"{prefix_time}, bạn không có lịch học nào trong lịch trình."
        elif len(events) == 1:
            ev = events[0]
            loc_txt = f" tại phòng {ev['location']}" if ev.get('location') else ""
            note_txt = f" (lịch học {ev['note'].lower()})" if ev.get('note') else ""
            code_txt = f" ({ev['code']})" if ev.get('code') else ""
            time_txt = f"từ {ev['time']}" if " - " in ev.get('time', '') else f"lúc {ev.get('time', '')}"
            speech = f"{prefix_time}, bạn có 1 lịch học: Môn {ev['title']}{code_txt} {time_txt}{loc_txt}{note_txt}."
        else:
            # Khi có 2, 3, 4 hoặc nhiều sự kiện: Đọc đầy đủ toàn bộ sự kiện theo thứ tự sáng đến chiều!
            items_speech = []
            ordinal_vi = ["Thứ nhất", "Thứ hai", "Thứ ba", "Thứ tư", "Thứ năm", "Thứ sáu", "Thứ bảy", "Thứ tám"]
            for idx, ev in enumerate(events):
                ord_prefix = ordinal_vi[idx] if idx < len(ordinal_vi) else f"Sự kiện {idx + 1}"
                loc_txt = f" tại phòng {ev['location']}" if ev.get('location') else ""
                note_txt = f" (lịch học {ev['note'].lower()})" if ev.get('note') else ""
                code_txt = f" ({ev['code']})" if ev.get('code') else ""
                time_txt = f"từ {ev['time']}" if " - " in ev.get('time', '') else f"lúc {ev.get('time', '')}"
                items_speech.append(f"{ord_prefix} là môn {ev['title']}{code_txt} {time_txt}{loc_txt}{note_txt}")

            speech = f"{prefix_time}, bạn có {len(events)} lịch học. " + ". ".join(items_speech) + "."

        # Chuẩn bị dữ liệu cho widget hiển thị ở BOTTOM_RIGHT
        widget_events = []
        for ev in events:
            widget_events.append({
                "title": ev["title"],
                "code": ev["code"],
                "time": ev["time"],
                "start_time": ev["start_time"],
                "end_time": ev["end_time"],
                "location": ev["location"],
                "note": ev.get("note", "")
            })

        return {
            "action": "GET_CALENDAR",
            "date_label": date_full_label,
            "target_date": target_date.strftime("%Y-%m-%d"),
            "count": len(widget_events),
            "events": widget_events,
            "response_text": speech
        }


# Singleton instance để tái sử dụng
_calendar_service_instance = None

def get_calendar_service() -> CalendarService:
    global _calendar_service_instance
    if _calendar_service_instance is None:
        _calendar_service_instance = CalendarService()
    return _calendar_service_instance

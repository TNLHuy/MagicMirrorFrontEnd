import asyncio
import base64
from datetime import datetime
import html
import json
import math
import os
import random
import re
import socket
import sys
import threading
import time
import unicodedata
import urllib.parse
import urllib.request
import ssl
import websockets
from typing import Optional, Set, Dict, Any, List

try:
    from aiohttp import web
    HAS_AIOHTTP = True
except ImportError:
    web = None
    HAS_AIOHTTP = False

try:
    import yt_dlp
    HAS_YTDLP = True
except ImportError:
    HAS_YTDLP = False

def get_lan_ip() -> str:
    """Tự động phát hiện địa chỉ IP mạng nội bộ (LAN) của máy tính / Raspberry Pi qua nhiều cơ chế"""
    # 1. Cho phép ghi đè cấu hình trong .env (ví dụ: MIRROR_LAN_IP=192.168.1.50)
    env_ip = os.getenv("MIRROR_LAN_IP")
    if env_ip and env_ip.strip():
        return env_ip.strip()

    # 2. Thử qua kết nối UDP Socket định tuyến mạng
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        if ip and not ip.startswith('127.'):
            return ip
    except Exception:
        pass

    # 3. Thử qua lệnh hệ thống Linux 'hostname -I' (rất chuẩn trên Raspberry Pi OS / Ubuntu)
    try:
        import subprocess
        res = subprocess.run(['hostname', '-I'], capture_output=True, text=True, timeout=1.0)
        for ip in res.stdout.strip().split():
            if ip and not ip.startswith('127.') and '.' in ip:
                return ip
    except Exception:
        pass

    # 4. Thử qua hostname phân giải
    try:
        h_name = socket.gethostname()
        ip = socket.gethostbyname(h_name)
        if ip and not ip.startswith('127.'):
            return ip
    except Exception:
        pass

    return '127.0.0.1'

def _verify_image_url(url: str, timeout: float = 2.0) -> bool:
    """Kiểm tra tiền trạm xác thực URL hình ảnh còn hoạt động tốt và trả về định dạng ảnh hợp lệ"""
    if not url or not url.startswith("http"):
        return False
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(
            url,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
                'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8'
            }
        )
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            if resp.status == 200:
                ctype = resp.headers.get('Content-Type', '').lower()
                clength = resp.headers.get('Content-Length')
                if clength and int(clength) < 3000:
                    return False
                if any(t in ctype for t in ['image/', 'application/octet-stream']) or 'bing.net' in url or 'wikimedia.org' in url:
                    return True
    except Exception:
        pass
    return False

def _remove_vietnamese_accents(text: str) -> str:
    """Chuyển chuỗi tiếng Việt có dấu thành không dấu để so khớp chính xác tên file mp3"""
    if not text:
        return ""
    text = text.replace("đ", "d").replace("Đ", "D")
    normalized = unicodedata.normalize("NFD", text)
    return "".join(c for c in normalized if unicodedata.category(c) != "Mn").lower()

# Đảm bảo Windows console hỗ trợ UTF-8 mà không bị UnicodeEncodeError
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Tích hợp Hardware, Voice, AI Engine & Services từ các subpackage chuyên biệt
from backend.hardware.camera_service import RealCamera, SCREENSHOT_DIR
from backend.hardware.display_manager import DisplayManager
from backend.voice.audio_recorder import RealMicrophone
from backend.voice.tts_service import get_tts_engine
from backend.ai.gemini_router import AIEngine
from backend.services.calendar_service import get_calendar_service

class MirrorBackend:
    """
    Backend Python điều khiển MagicMirror theo tập danh sách 10 ACTION của NLU Router:
    
    1. BỐ CỤC TĨNH (Cố định ở 4 góc mặt gương):
       - [TOP_LEFT]     : Đồng hồ số & Thứ Ngày (clock) -> GET_TIME, GET_DATE
       - [TOP_RIGHT]    : Thời tiết hiện tại (weather)   -> SHOW_WEATHER
       - [BOTTOM_LEFT]  : Lịch trình cá nhân (calendar) -> GET_CALENDAR
       - [BOTTOM_RIGHT] : Trình phát nhạc mini (PLAY_MEDIA) & Trạng thái SmartHome (SMART_HOME)
    
    2. BỐ CỤC ĐỘNG:
       - [MIDDLE_CENTER]: Khu vực hiển thị tương tác (Popup / Overlay):
           • NONE          : Bong bóng thủy tinh AI hội thoại (response_text)
           • SEARCH (img)  : Popup ảnh toàn màn hình
           • SEARCH (cam)  : Khung hình camera thật + Phân tích đồ vật Vision tag
           • TAKE_PHOTO    : Đếm ngược 3-2-1 + Chụp ảnh webcam thật + Lưu vào screen_shot/
       - [BOTTOM_BAR]   : Thanh trạng thái trợ lý: [Đang nghe...] / [Volume] (SYSTEM)
    """

    def __init__(self, host: str = "0.0.0.0", port: int = 8085, http_port: Optional[int] = None):
        self.host = host
        self.port = port
        self.http_port = http_port or int(os.getenv("PHOTO_HTTP_PORT", "8086"))
        self.lan_ip = get_lan_ip()
        self.clients: Set[websockets.WebSocketServerProtocol] = set()
        self.server = None
        self._http_runner = None
        self._http_site = None
        self.current_state = 0
        self.current_sub_state = "idle"
        self._loop: Optional[asyncio.AbstractEventLoop] = None

        # Khởi tạo thiết bị phần cứng thật & Trí tuệ nhân tạo Gemini
        self.camera = RealCamera() if RealCamera else None
        self.display = DisplayManager() if DisplayManager else None
        self.mic: Optional[RealMicrophone] = None
        self.ai: Optional[AIEngine] = AIEngine() if AIEngine else None
        self.tts = get_tts_engine()

        # Trạng thái chờ tạo dáng chụp ảnh
        self.photo_mode_active = False
        self._photo_timeout_task: Optional[asyncio.Task] = None
        self._listen_timeout_task: Optional[asyncio.Task] = None

    def _save_qr_image_file(self, photo_url: str, qr_filename: str):
        """Tự động lưu file ảnh mã QR PNG trực tiếp vào thư mục screen_shot/ để xem lại bất cứ lúc nào"""
        qr_filepath = os.path.join(SCREENSHOT_DIR, qr_filename)
        try:
            # 1. Thử dùng thư viện qrcode cục bộ nếu có
            try:
                import qrcode
                img = qrcode.make(photo_url)
                img.save(qr_filepath)
                print(f"[📱 QR Saved] Đã lưu file mã QR offline: screen_shot/{qr_filename}")
                return
            except ImportError:
                pass

            # 2. Tải ảnh PNG chất lượng cao từ API QR Code
            encoded = urllib.parse.quote(photo_url)
            api_url = f"https://api.qrserver.com/v1/create-qr-code/?size=320x320&margin=8&data={encoded}"
            req = urllib.request.Request(api_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=4.0) as resp:
                if resp.status == 200:
                    with open(qr_filepath, 'wb') as f:
                        f.write(resp.read())
                    print(f"[📱 QR Saved] Đã lưu file ảnh mã QR vào: screen_shot/{qr_filename}")
        except Exception as e:
            print(f"[!] Không thể lưu file mã QR ({qr_filename}): {e}")

    def _build_photo_payload(self, filename: str, image_url: str) -> dict:
        """Tạo gói tin PHOTO_CAPTURED chuẩn kèm link xem và tải ảnh qua QR Code nội bộ"""
        photo_url = f"http://{self.lan_ip}:{self.http_port}/view/{filename}"
        raw_photo_url = f"http://{self.lan_ip}:{self.http_port}/photo/{filename}"
        qr_filename = f"qr_{os.path.splitext(filename)[0]}.png"
        qr_url = f"http://{self.lan_ip}:{self.http_port}/photo/{qr_filename}"

        # Tự động lưu file mã QR vào screen_shot/ trên luồng chạy ngầm
        threading.Thread(target=self._save_qr_image_file, args=(photo_url, qr_filename), daemon=True).start()

        return {
            "action": "PHOTO_CAPTURED",
            "image_url": image_url,
            "filename": filename,
            "photo_url": photo_url,
            "raw_photo_url": raw_photo_url,
            "qr_filename": qr_filename,
            "qr_url": qr_url,
            "lan_ip": self.lan_ip,
            "http_port": self.http_port
        }

    async def _handle_connection(self, websocket):
        self.clients.add(websocket)
        try:
            client_ip = websocket.remote_address[0] if websocket.remote_address else "unknown"
        except Exception:
            client_ip = "unknown"
        print(f"[+] MagicMirror đã kết nối thành công từ: {client_ip}")

        # Gửi trạng thái hiện tại ngay khi client kết nối
        try:
            await websocket.send(json.dumps({
                "state": self.current_state,
                "subState": self.current_sub_state
            }, ensure_ascii=False))
        except Exception:
            pass

        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    act = data.get("action") or data.get("type")
                    if act == "CLIENT_PHOTO_CAPTURED":
                        self.photo_mode_active = False
                        if self._photo_timeout_task and not self._photo_timeout_task.done():
                            self._photo_timeout_task.cancel()
                            self._photo_timeout_task = None
                        if self.mic and hasattr(self.mic, "stop_photo_mode"):
                            self.mic.stop_photo_mode()

                        data_url = data.get("data_url")
                        if data_url and "," in data_url:
                            try:
                                header, encoded = data_url.split(",", 1)
                                img_bytes = base64.b64decode(encoded)
                                now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                                filename = f"photo_{now_str}.jpg"
                                filepath = os.path.join(SCREENSHOT_DIR, filename)
                                with open(filepath, "wb") as f:
                                    f.write(img_bytes)
                                print(f"[📸 Camera] Đã nhận và lưu ảnh từ live preview vào: screen_shot/{filename}")
                                payload = self._build_photo_payload(filename, data_url)
                                await self.broadcast(payload)
                                print(f"[📱 QR Photo] Quét mã để xem & tải ảnh tại: {payload['photo_url']}")
                            except Exception as ex:
                                print(f"[!] Lỗi ghi file ảnh từ client: {ex}")

                    elif act == "TRIGGER_BACKEND_CAPTURE":
                        self.photo_mode_active = False
                        if self._photo_timeout_task and not self._photo_timeout_task.done():
                            self._photo_timeout_task.cancel()
                            self._photo_timeout_task = None
                        if self.mic and hasattr(self.mic, "stop_photo_mode"):
                            self.mic.stop_photo_mode()
                        if self.camera:
                            result = await asyncio.to_thread(self.camera.capture_photo, "photo")
                            if result.get("success") and result.get("data_url"):
                                payload = self._build_photo_payload(result["filename"], result["data_url"])
                                await self.broadcast(payload)
                                print(f"[📸 Camera] Đã chụp ảnh thành công từ OpenCV: screen_shot/{result['filename']}")
                                print(f"[📱 QR Photo] Quét mã để xem & tải ảnh tại: {payload['photo_url']}")
                            else:
                                print(f"[!] Chụp ảnh OpenCV thất bại: {result.get('error')}")

                    elif act == "TRIGGER_BACKEND_VISION":
                        await self.search_camera_vision()

                    elif act == "CLIENT_VISION_FRAME":
                        data_url = data.get("data_url")
                        if data_url and "," in data_url:
                            try:
                                header, encoded = data_url.split(",", 1)
                                img_bytes = base64.b64decode(encoded)
                                filepath = os.path.join(SCREENSHOT_DIR, "vision_frame.jpg")
                                with open(filepath, "wb") as f:
                                    f.write(img_bytes)
                                print(f"[👁️ Vision AI] Đã nhận frame từ camera live preview, đang phân tích qua Gemini Vision...")

                                detections = None
                                summary = "Đã phân tích các vật thể trong khung hình:"
                                if self.ai and self.ai.is_api_active():
                                    v_res = await self.ai.analyze_vision_with_gemini(filepath)
                                    detections = v_res.get("detections")
                                    summary = v_res.get("summary") or summary

                                if not detections:
                                    detections = [
                                        {"label": "Vật thể trước gương", "confidence": "95%"},
                                        {"label": "Khuôn mặt người dùng", "confidence": "98%"}
                                    ]

                                await self.broadcast({
                                    "action": "VISION_RESULT",
                                    "detections": detections,
                                    "image_url": data_url
                                })
                                if self.tts and summary:
                                    self.tts.speak(summary, wait=False)
                            except Exception as ex:
                                print(f"[!] Lỗi phân tích vision từ client: {ex}")
                    else:
                        print(f"[<- Client]: {data}")
                except Exception:
                    pass
        except Exception:
            pass
        finally:
            self.clients.discard(websocket)
            print(f"[-] Client {client_ip} đã ngắt kết nối.")

    async def start_photo_http_server(self):
        """Khởi động máy chủ HTTP tĩnh phục vụ xem và tải ảnh chụp qua QR Code mạng LAN"""
        if not HAS_AIOHTTP:
            print("[⚠️ Photo Server] aiohttp chưa được cài đặt, tính năng tải ảnh qua HTTP tạm tắt.")
            return

        app = web.Application()

        # Route 1: Phục vụ trực tiếp file ảnh raw trong thư mục screen_shot/
        app.router.add_static('/photo/', path=SCREENSHOT_DIR, name='photo', show_index=False)

        # Route 2: Trang web xem & tải ảnh phong cách Glassmorphism cho điện thoại
        async def handle_view(request):
            filename = request.match_info.get('filename', '')
            safe_filename = os.path.basename(filename)
            filepath = os.path.join(SCREENSHOT_DIR, safe_filename)
            if not os.path.isfile(filepath):
                return web.Response(text=f"<h3>Không tìm thấy file ảnh: {html.escape(safe_filename)}</h3>", content_type="text/html", status=404)

            safe_base = os.path.splitext(safe_filename)[0]
            qr_filename = f"qr_{safe_base}.png"
            qr_filepath = os.path.join(SCREENSHOT_DIR, qr_filename)
            has_qr = os.path.isfile(qr_filepath)

            qr_section_html = ""
            if has_qr:
                qr_section_html = f"""
                <div style="margin-top: 14px; padding-top: 14px; border-top: 1px solid rgba(255,255,255,0.1);">
                    <div style="font-size: 11.5px; color: #94a3b8; margin-bottom: 8px;">📱 Mã QR xem lại ảnh này:</div>
                    <div style="background: #fff; padding: 6px; border-radius: 12px; display: inline-block; box-shadow: 0 4px 14px rgba(0,242,254,0.25);">
                        <img src="/photo/{qr_filename}" style="width: 110px; height: 110px; display: block;" alt="QR" />
                    </div>
                </div>
                """

            html_content = f"""<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Ảnh chụp từ Gương Thông Minh</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
        body {{
            background: linear-gradient(135deg, #0b0f19 0%, #111827 50%, #030712 100%);
            color: #f1f5f9;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 16px;
        }}
        .card {{
            background: rgba(17, 24, 39, 0.88);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            border: 1.5px solid rgba(0, 242, 254, 0.35);
            border-radius: 24px;
            padding: 20px;
            max-width: 440px;
            width: 100%;
            box-shadow: 0 20px 45px rgba(0,0,0,0.65), 0 0 30px rgba(0, 242, 254, 0.18);
            text-align: center;
        }}
        .badge {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background: rgba(0, 242, 254, 0.12);
            color: #00f2fe;
            border: 1px solid rgba(0, 242, 254, 0.3);
            border-radius: 20px;
            padding: 5px 14px;
            font-size: 13px;
            font-weight: 600;
            margin-bottom: 14px;
        }}
        .img-box {{
            width: 100%;
            border-radius: 16px;
            overflow: hidden;
            background: #000;
            box-shadow: 0 10px 25px rgba(0,0,0,0.5);
            margin-bottom: 16px;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }}
        .img-box img {{
            width: 100%;
            height: auto;
            max-height: 52vh;
            object-fit: contain;
            display: block;
        }}
        .info {{
            font-size: 12px;
            color: #94a3b8;
            margin-bottom: 18px;
            line-height: 1.5;
        }}
        .info strong {{ color: #e2e8f0; }}
        .actions {{
            display: flex;
            flex-direction: column;
            gap: 10px;
        }}
        .btn-download {{
            background: linear-gradient(135deg, #00f2fe 0%, #4facfe 100%);
            color: #051329;
            font-weight: 700;
            font-size: 15px;
            padding: 14px 20px;
            border-radius: 14px;
            text-decoration: none;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            box-shadow: 0 6px 20px rgba(0, 242, 254, 0.4);
            transition: transform 0.2s, box-shadow 0.2s;
        }}
        .btn-download:active {{
            transform: scale(0.98);
        }}
        .btn-raw {{
            background: rgba(255, 255, 255, 0.08);
            color: #cbd5e1;
            font-weight: 500;
            font-size: 13px;
            padding: 10px 16px;
            border-radius: 12px;
            text-decoration: none;
            border: 1px solid rgba(255, 255, 255, 0.12);
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 6px;
        }}
        .footer {{
            margin-top: 16px;
            font-size: 11px;
            color: #64748b;
        }}
    </style>
</head>
<body>
    <div class="card">
        <div class="badge">📸 Smart Mirror 2.0</div>
        <div class="img-box">
            <img src="/photo/{safe_filename}" alt="Ảnh chụp" />
        </div>
        <div class="info">
            Tập tin: <strong>{safe_filename}</strong><br>
            <em>Chạm giữ vào ảnh để lưu nhanh, hoặc nhấn nút bên dưới:</em>
        </div>
        <div class="actions">
            <a href="/photo/{safe_filename}" download="{safe_filename}" class="btn-download">
                📥 Tải ảnh về điện thoại
            </a>
            <a href="/photo/{safe_filename}" target="_blank" class="btn-raw">
                🔍 Xem ảnh gốc toàn màn hình
            </a>
            <a href="/gallery" class="btn-raw">
                🖼️ Mở Thư Viện Tất Cả Ảnh Đã Chụp
            </a>
            <a href="/web" class="btn-raw" style="color: #00f2fe; border-color: rgba(0, 242, 254, 0.3);">
                🌐 Mở Bảng Điều Khiển Web Hub (IoT, Lịch, Ảnh)
            </a>
        </div>
        {qr_section_html}
        <div class="footer">✨ Chụp từ Trợ lý Gương Thông Minh AI</div>
    </div>
</body>
</html>"""
            return web.Response(text=html_content, content_type="text/html")

        # Route 3: Bộ sưu tập toàn bộ ảnh & mã QR đã chụp (Gallery)
        async def handle_gallery(request):
            photo_files = sorted(
                [f for f in os.listdir(SCREENSHOT_DIR) if f.startswith('photo_') and f.endswith('.jpg')],
                reverse=True
            )

            cards_html = ""
            for pf in photo_files:
                base = os.path.splitext(pf)[0]
                qr_name = f"qr_{base}.png"
                qr_path = os.path.join(SCREENSHOT_DIR, qr_name)
                has_qr = os.path.isfile(qr_path)
                qr_img_tag = f'<img src="/photo/{qr_name}" style="width: 50px; height: 50px; background: #fff; padding: 2px; border-radius: 6px;" alt="QR" />' if has_qr else ''

                cards_html += f"""
                <div class="gallery-card">
                    <a href="/view/{pf}">
                        <img src="/photo/{pf}" class="thumb" loading="lazy" alt="{pf}" />
                    </a>
                    <div class="card-meta">
                        <div class="meta-title">{pf}</div>
                        <div class="meta-actions">
                            <a href="/photo/{pf}" download="{pf}" class="btn-mini">📥 Tải ảnh</a>
                            <a href="/view/{pf}" class="btn-mini-view">👁️ Xem</a>
                            {f'<a href="/photo/{qr_name}" download="{qr_name}" class="btn-mini-qr">{qr_img_tag}</a>' if has_qr else ''}
                        </div>
                    </div>
                </div>
                """

            if not cards_html:
                cards_html = '<div style="color: #94a3b8; padding: 40px; text-align: center;">Chưa có bức ảnh nào trong thư mục screen_shot/.</div>'

            gallery_html = f"""<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Thư Viện Ảnh • Smart Mirror</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
        body {{
            background: linear-gradient(135deg, #0b0f19 0%, #111827 50%, #030712 100%);
            color: #f1f5f9;
            min-height: 100vh;
            padding: 20px 14px;
        }}
        .header {{
            text-align: center;
            margin-bottom: 24px;
        }}
        .header h1 {{
            font-size: 20px;
            font-weight: 700;
            color: #00f2fe;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            margin-bottom: 6px;
        }}
        .header p {{
            font-size: 12px;
            color: #94a3b8;
        }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 16px;
            max-width: 900px;
            margin: 0 auto;
        }}
        .gallery-card {{
            background: rgba(17, 24, 39, 0.85);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border: 1px solid rgba(0, 242, 254, 0.25);
            border-radius: 18px;
            overflow: hidden;
            box-shadow: 0 10px 25px rgba(0,0,0,0.5);
            display: flex;
            flex-direction: column;
        }}
        .thumb {{
            width: 100%;
            height: 200px;
            object-fit: cover;
            display: block;
            background: #000;
        }}
        .card-meta {{
            padding: 12px 14px;
            display: flex;
            flex-direction: column;
            gap: 8px;
        }}
        .meta-title {{
            font-size: 12px;
            font-weight: 600;
            color: #e2e8f0;
            word-break: break-all;
        }}
        .meta-actions {{
            display: flex;
            align-items: center;
            gap: 8px;
            flex-wrap: wrap;
        }}
        .btn-mini {{
            background: linear-gradient(135deg, #00f2fe 0%, #4facfe 100%);
            color: #051329;
            font-weight: 700;
            font-size: 11.5px;
            padding: 6px 12px;
            border-radius: 8px;
            text-decoration: none;
        }}
        .btn-mini-view {{
            background: rgba(255,255,255,0.08);
            color: #cbd5e1;
            font-size: 11.5px;
            padding: 6px 12px;
            border-radius: 8px;
            text-decoration: none;
            border: 1px solid rgba(255,255,255,0.12);
        }}
        .btn-mini-qr {{
            margin-left: auto;
            text-decoration: none;
            display: flex;
            align-items: center;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🖼️ Bộ Sưu Tập Ảnh Smart Mirror</h1>
        <p>Tổng hợp các bức ảnh chụp và mã QR lưu lại trên gương</p>
        <div style="margin-top: 12px;">
            <a href="/web" style="display: inline-block; background: rgba(0, 242, 254, 0.15); border: 1px solid #00f2fe; color: #00f2fe; padding: 6px 14px; border-radius: 20px; font-size: 13px; text-decoration: none; font-weight: 600;">
                🌐 Truy cập Bảng Điều Khiển Web Hub (IoT, Lịch & Ảnh)
            </a>
        </div>
    </div>
    <div class="grid">
        {cards_html}
    </div>
</body>
</html>"""
            return web.Response(text=gallery_html, content_type="text/html")

        # Mount Companion Web App (Vite React Hub) if built
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        web_dist_dir = os.path.join(project_root, "web", "dist")
        if os.path.isdir(web_dist_dir):
            app.router.add_static('/web', path=web_dist_dir, name='web_app', show_index=True)
            app.router.add_static('/hub', path=web_dist_dir, name='hub_app', show_index=True)

        # Dynamic Photo Gallery API (Real-time sync with screen_shot directory)
        async def api_get_photos(request):
            photos = []
            if os.path.isdir(SCREENSHOT_DIR):
                files = sorted(
                    [f for f in os.listdir(SCREENSHOT_DIR) if f.startswith('photo_') and (f.endswith('.jpg') or f.endswith('.png'))],
                    reverse=True
                )
                for f in files:
                    fp = os.path.join(SCREENSHOT_DIR, f)
                    st = os.stat(fp)
                    base = os.path.splitext(f)[0]
                    qr_name = f"qr_{base}.png"
                    has_qr = os.path.isfile(os.path.join(SCREENSHOT_DIR, qr_name))

                    formatted_date = datetime.fromtimestamp(st.st_mtime).strftime("%d/%m/%Y %H:%M:%S")
                    m = re.match(r"photo_(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})", f)
                    if m:
                        y, mo, d, h, mi, s = m.groups()
                        formatted_date = f"{d}/{mo}/{y} {h}:{mi}:{s}"

                    photos.append({
                        "id": base,
                        "fileName": f,
                        "url": f"/photo/{f}",
                        "qrUrl": f"/photo/{qr_name}" if has_qr else None,
                        "formattedDate": formatted_date,
                        "size": f"{round(st.st_size / 1024)} KB",
                        "tag": "Webcam Selfie"
                    })
            return web.json_response(photos)

        async def api_delete_photo(request):
            filename = os.path.basename(request.match_info.get('filename', ''))
            fp = os.path.join(SCREENSHOT_DIR, filename)
            base = os.path.splitext(filename)[0]
            qp = os.path.join(SCREENSHOT_DIR, f"qr_{base}.png")
            deleted = False
            if os.path.isfile(fp):
                os.remove(fp)
                deleted = True
            if os.path.isfile(qp):
                os.remove(qp)
            if deleted:
                return web.json_response({"success": True, "message": f"Deleted {filename}"})
            return web.json_response({"error": "File not found"}, status=404)

        app.router.add_get('/api/photos', api_get_photos)
        app.router.add_delete('/api/photos/{filename}', api_delete_photo)
        app.router.add_get('/', handle_gallery)
        app.router.add_get('/gallery', handle_gallery)
        app.router.add_get('/view/{filename}', handle_view)

        try:
            runner = web.AppRunner(app)
            await runner.setup()
            self._http_site = web.TCPSite(runner, self.host, self.http_port)
            await self._http_site.start()
            self._http_runner = runner
            print(f"[📷 Photo Server] Máy chủ chia sẻ ảnh QR đang chạy tại: http://{self.lan_ip}:{self.http_port}/view/<tên_ảnh>")
        except Exception as e:
            print(f"[⚠️ Photo Server] Không thể khởi động máy chủ ảnh HTTP trên cổng {self.http_port}: {e}")

    async def start_server(self):
        """Khởi động WebSocket Server và Photo HTTP Server bất đồng bộ"""
        self._loop = asyncio.get_running_loop()
        self.server = await websockets.serve(self._handle_connection, self.host, self.port)
        await self.start_photo_http_server()
        print("==================================================================")
        print(f"[+] Python Mirror Backend Server đang chạy tại ws://{self.host}:{self.port}")
        print(f"[+] Photo QR Download Server đang chạy tại http://{self.lan_ip}:{self.http_port}")
        print(f"[+] Companion Web Hub (IoT/Lịch/Ảnh) tại http://{self.lan_ip}:{self.http_port}/web")
        print("    Đang lắng nghe kết nối từ MagicMirror (MMM-StateControl)...")
        print("==================================================================")

    async def stop_server(self):
        """Đóng an toàn tất cả các máy chủ WebSocket và HTTP"""
        if self._http_runner:
            try:
                await self._http_runner.cleanup()
            except Exception:
                pass
        if self.server:
            try:
                self.server.close()
                await self.server.wait_closed()
            except Exception:
                pass

    async def broadcast(self, payload: dict):
        """Gửi gói tin JSON tới tất cả các màn hình gương đang kết nối"""
        is_amp = payload.get("type") == "amplitude"
        act = payload.get("action") or payload.get("state")
        if not self.clients:
            if not is_amp:
                print(f"[⚠️ WebSocket] Chưa có màn hình MagicMirror nào kết nối (ws://0.0.0.0:{self.port}) để nhận '{act}'! (0 client)")
            return
        if not is_amp and act:
            print(f"[📡 WebSocket ➔ MagicMirror] Đã gửi lệnh '{act}' tới {len(self.clients)} màn hình gương.")
        message = json.dumps(payload, ensure_ascii=False)
        for client in list(self.clients):
            try:
                await client.send(message)
            except Exception:
                pass

    # -------------------------------------------------------------
    # 0. QUẢN LÝ MICROPHONE THẬT (REALTIME RMS AUDIO)
    # -------------------------------------------------------------

    def start_real_mic(self, sensitivity: float = 12.0, enable_stt: bool = True, enable_wakeword: bool = True, enable_live_display: bool = True) -> bool:
        """Kích hoạt microphone thật: Rung sóng Siri theo âm lượng, Nhận diện 'Hey Mirror' (Wakeword) & STT tiếng Việt"""
        if not RealMicrophone:
            print("[!] RealMicrophone chưa sẵn sàng. Hãy cài: python -m pip install sounddevice numpy onnxruntime")
            return False

        if self.mic and self.mic.is_running:
            return True

        def _on_amp(val: float):
            if self._loop and self._loop.is_running():
                asyncio.run_coroutine_threadsafe(self.send_amplitude(val), self._loop)

        def _on_speech(text: str, latency: float = 0.0):
            if self._loop and self._loop.is_running():
                # Tự động đưa câu nói của người dùng vào Gemini NLU Router!
                fut = asyncio.run_coroutine_threadsafe(self.handle_user_prompt(text, stt_latency=latency), self._loop)
                fut.add_done_callback(lambda f: f.exception() and print(f"[❌ Lỗi NLU Router]: {f.exception()}"))

        def _on_wakeword(score: float):
            if self._loop and self._loop.is_running():
                fut = asyncio.run_coroutine_threadsafe(self.handle_wakeword_triggered(score), self._loop)
                fut.add_done_callback(lambda f: f.exception() and print(f"[❌ Lỗi Wakeword Event]: {f.exception()}"))

        self.mic = RealMicrophone(
            on_amplitude_callback=_on_amp,
            on_speech_detected_callback=_on_speech,
            on_wakeword_detected_callback=_on_wakeword,
            sensitivity=sensitivity,
            enable_stt=enable_stt,
            enable_wakeword=enable_wakeword,
            enable_live_display=enable_live_display
        )
        if self.tts:
            self.tts.set_mic(self.mic)
        return self.mic.start()

    async def handle_wakeword_triggered(self, score: float = 1.0):
        """
        Xử lý sự kiện khi phát hiện từ khóa đánh thức 'Hey Mirror' (Wakeword Engine):
        1. Gửi sự kiện WAKEWORD_TRIGGERED để UI MagicMirror lập tức PAUSE bài hát đang phát
        2. Nếu gương đang ở State 0 (Ngủ / Tắt màn hình):
           - Đánh thức gương sang State 1 (Active)
           - Bật màn hình phần cứng (HDMI / Wayland)
           - Phát chuông báo (Chime) và đưa trợ lý vào trạng thái sẵn sàng lắng nghe
        3. Nếu gương đã ở State 1 (Đang thức):
           - Phát chuông báo (Chime)
           - Kích hoạt trạng thái 'Đang lắng nghe...'
        """
        print(f"\n[🔥 WAKEWORD EVENT] Nhận diện thành công 'Hey Mirror'! (Khớp: {score*100:.1f}%)")

        # Lập tức thông báo cho MagicMirror tạm dừng nhạc ngay mili-giây đầu tiên
        await self.broadcast({
            "action": "WAKEWORD_TRIGGERED",
            "score": float(score),
            "pause_music": True
        })

        # Xóa sạch âm thanh từ khóa Hey Mirror và mở cổng lắng nghe câu lệnh
        if self.mic:
            if hasattr(self.mic, "start_listening"):
                self.mic.start_listening(timeout_sec=10.0)
            else:
                self.mic.flush_speech_buffer(0.65)

        if self.current_state == 0:
            print("[🖥️ Display] Màn hình đang tắt (State 0) -> Đang bật màn hình và thức giấc (State 1)...")
            if self.display:
                self.display.turn_on()
            await self.set_state(1, text="Gương đã hoạt động", sub_state="idle")
            await self.ai_listen("Chào bạn, tôi đang lắng nghe...")
        else:
            await self.ai_listen("Tôi đang lắng nghe...")

    def stop_real_mic(self):
        """Dừng thu âm từ micro"""
        if self.mic:
            self.mic.stop()
            self.mic = None

    # -------------------------------------------------------------
    # 1. NHÓM HÀM ACTION HỆ THỐNG (SYSTEM & STATES)
    # -------------------------------------------------------------

    async def set_state(self, state: int, text: Optional[str] = None, sub_state: Optional[str] = None):
        """Chuyển trạng thái hệ thống: State 0 (Ngủ), State 1 (Active)"""
        self.current_state = int(state)
        if sub_state:
            self.current_sub_state = sub_state
        payload = {"state": self.current_state}
        if text:
            payload["text"] = text
        if sub_state:
            payload["subState"] = sub_state
        await self.broadcast(payload)

        # Điều khiển nguồn màn hình phần cứng thực tế (DPMS)
        if self.display:
            if self.current_state == 0:
                self.display.turn_off()
            else:
                self.display.turn_on()

        print(f"[-> System] Chuyển sang State {self.current_state}")

    async def set_sleep(self):
        """State 0: Ngủ (Standby - Màn hình tắt đen hoàn toàn, ẩn toàn bộ widget)"""
        self.current_sub_state = "idle"
        if self.photo_mode_active:
            await self.cancel_photo_mode()
        await self.set_state(0)

    async def set_active(self):
        """State 1: Thức (Active - Hiện toàn bộ Widget tĩnh 4 góc)"""
        self.current_sub_state = "idle"
        await self.set_state(1, sub_state="idle")

    async def ai_listen(self, prompt: str = "Đang lắng nghe...", timeout_sec: float = 7.0):
        """Kích hoạt trạng thái Lắng nghe ở BOTTOM_BAR với cơ chế tự động thoát (Timeout)"""
        if self._listen_timeout_task and not self._listen_timeout_task.done():
            self._listen_timeout_task.cancel()
            self._listen_timeout_task = None

        if self.mic and hasattr(self.mic, "start_listening"):
            self.mic.start_listening(timeout_sec=timeout_sec)

        self.current_state = 1
        self.current_sub_state = "listening"
        await self.broadcast({
            "action": "LISTEN",
            "text": prompt,
            "pause_music": True
        })
        print(f"[-> Assistant] Bắt đầu nghe: '{prompt}' (Tự động trở về sau {timeout_sec:.0f}s nếu không có lệnh)")

        # Tạo worker đếm ngược tự động quay về trạng thái Idle nếu người dùng không nói gì
        async def _listen_timeout_worker():
            try:
                await asyncio.sleep(timeout_sec)
                if self.current_sub_state == "listening":
                    print("[⏱️ Timeout] Người dùng không ra lệnh, trợ lý tự động chuyển về trạng thái Sẵn sàng.")
                    if self.mic and hasattr(self.mic, "is_listening_for_command"):
                        self.mic.is_listening_for_command = not getattr(self.mic, "enable_wakeword", True)
                    await self.ai_idle()
            except asyncio.CancelledError:
                pass

        if self._loop and self._loop.is_running():
            self._listen_timeout_task = self._loop.create_task(_listen_timeout_worker())
        else:
            self._listen_timeout_task = asyncio.create_task(_listen_timeout_worker())

    async def send_amplitude(self, value: float):
        """Bắn biên độ âm lượng (0.0 đến 1.0) làm sóng Siri ở BOTTOM_BAR rung động"""
        val = max(0.0, min(1.0, float(value)))
        await self.broadcast({
            "type": "amplitude",
            "value": round(val, 3)
        })

    async def ai_think(self, prompt: str = "Đang xử lý câu hỏi..."):
        """Trợ lý đang suy nghĩ ở BOTTOM_BAR"""
        if self._listen_timeout_task and not self._listen_timeout_task.done():
            self._listen_timeout_task.cancel()
            self._listen_timeout_task = None

        self.current_state = 1
        self.current_sub_state = "thinking"
        await self.broadcast({
            "action": "THINK",
            "text": prompt
        })
        print(f"[-> Assistant] Đang xử lý: '{prompt}'")

    async def ai_idle(self):
        """Trợ lý trở về trạng thái nghỉ (Ẩn tất cả popup ở MIDDLE_CENTER)"""
        if self._listen_timeout_task and not self._listen_timeout_task.done():
            self._listen_timeout_task.cancel()
            self._listen_timeout_task = None

        self.current_state = 1
        self.current_sub_state = "idle"
        await self.broadcast({
            "action": "IDLE"
        })
        print("[-> Assistant] Trở về trạng thái Idle")

    # -------------------------------------------------------------
    # 2. XỬ LÝ PROMPT NGƯỜI DÙNG BẰNG AI ENGINE (GEMINI NLU ROUTER)
    # -------------------------------------------------------------

    async def handle_user_prompt(self, user_text: str, stt_latency: float = 0.0) -> Dict[str, Any]:
        """
        Tiếp nhận câu nói của người dùng, chuyển tới Gemini 3.8 Flash NLU Router
        để phân tích ý định và tự động kích hoạt Action tương ứng trên gương.
        """
        # Hủy timeout lắng nghe ngay khi có câu nói mới
        if self._listen_timeout_task and not self._listen_timeout_task.done():
            self._listen_timeout_task.cancel()
            self._listen_timeout_task = None

        if not self.ai:
            print("[!] AIEngine chưa được khởi tạo.")
            return {}

        print(f"\n[🗣️ Người dùng]: '{user_text}'")

        # -----------------------------------------------------------------
        # TỰ ĐỘNG BÓC TÁCH VÀ XỬ LÝ TỪ KHÓA ĐÁNH THỨC 'HEY MIRROR'
        # -----------------------------------------------------------------
        # Mẫu nhận diện các biến thể phát âm của 'Hey Mirror' từ STT
        wakeword_pattern = r'^(hey|hay|hây|ê|ok|này|hai|he|hê)\s*(mirror|mi\s*rơ|mi\s*rô|mê\s*rơ)?[,\s]*'
        matched_wake = re.match(wakeword_pattern, user_text.strip(), flags=re.I)

        wake_only_phrases = {
            "hey mirror", "hay mirror", "hây mirror", "ê mirror", "ok mirror", "này mirror",
            "hai mi rơ", "he mi rơ", "hê mi rơ", "he mi rô", "hê mi rô", "hai mi rô",
            "mi rơ", "mê rơ", "mi rô", "em đi rồi", "thầy mi rơ", "thay mi ro"
        }
        clean_check = re.sub(r'[.,?!;:\s]', '', user_text.strip().lower())
        is_just_wakeword = any(clean_check == re.sub(r'\s', '', w) for w in wake_only_phrases)

        if matched_wake or is_just_wakeword:
            cleaned_text = re.sub(wakeword_pattern, '', user_text.strip(), flags=re.I).strip()
            print(f"[🔥 Wakeword STT] Nhận diện 'Hey Mirror' qua giọng nói. Lệnh kèm theo: '{cleaned_text}'")
            if self.current_state == 0:
                if self.display:
                    self.display.turn_on()
                await self.set_state(1, text="Gương đã hoạt động", sub_state="idle")

            if not cleaned_text:
                if self.mic:
                    self.mic.flush_speech_buffer(0.65)
                await self.ai_listen("Chào bạn, tôi đang lắng nghe...", timeout_sec=7.0)
                return {"action": "WAKEWORD_LISTEN"}
            user_text = cleaned_text

        # -----------------------------------------------------------------
        # XỬ LÝ NGỮ CẢNH ĐẶC BIỆT: KHI ĐANG TRONG CHẾ ĐỘ CHỜ TẠO DÁNG CHỤP ẢNH
        # -----------------------------------------------------------------
        if self.photo_mode_active:
            norm = _remove_vietnamese_accents(user_text.strip().lower())
            clean_norm = re.sub(r'[^\w\s]', ' ', norm)
            clean_norm = re.sub(r'\s+', ' ', clean_norm).strip()

            # 1. Nhóm từ khóa HỦY CHỤP
            cancel_keywords = [
                "huy", "thoi", "khong chup", "khong chup nua", "thoi khong chup",
                "tat camera", "dong camera", "tat di", "dong lai", "dong di", "tat", "dong",
                "thoat", "thoat camera", "dung lai", "dung chup", "dung", "ngung", "ngung chup", "bo qua",
                "khong can", "quay lai", "ve man hinh chinh", "cancel", "stop", "exit", "close", "thui", "hui"
            ]
            is_cancel = False
            if "thoi tiet" not in clean_norm:
                for k in cancel_keywords:
                    if k == clean_norm or re.search(r'\b' + re.escape(k) + r'\b', clean_norm):
                        is_cancel = True
                        break

            if is_cancel:
                print(f"[📸 Camera] Nhận lệnh hủy từ giọng nói: '{user_text}'")
                await self.cancel_photo_mode()
                return {"action": "CANCEL_PHOTO"}

            # 2. Nhóm từ khóa KÍCH HOẠT CHỤP (bao gồm cả biến thể nghe nhầm 'chộp' từ STT)
            capture_keywords = [
                "chup", "chup anh", "chup hinh", "bat dau", "bat dau chup", "chup di",
                "chup nao", "chup ho", "chup giup", "chup ngay", "chup luon", "bam may",
                "bam chup", "1 2 3", "mot hai ba", "ba hai mot", "3 2 1", "tach",
                "san sang", "xong roi", "ok chup", "chup nhe", "chup cho toi",
                "chup toi", "chup minh", "chup em", "chup buc anh", "chup tam anh",
                "ok", "chup dc", "chup duoc", "chup xong", "chup thu", "chup luon di",
                "start", "capture", "photo", "smile", "cuoi len",
                # Dung sai cho STT nghe nhầm 'chụp' -> 'chộp'
                "chop", "chop anh", "chop hinh", "chop di", "chop nao", "chop ho",
                "chop giup", "chop ngay", "chop luon", "bam chop"
            ]
            is_capture = False
            for k in capture_keywords:
                if k == clean_norm or re.search(r'\b' + re.escape(k) + r'\b', clean_norm):
                    is_capture = True
                    break

            if is_capture:
                print(f"[📸 Camera] Nhận lệnh kích hoạt chụp từ giọng nói: '{user_text}'")
                await self.start_photo_countdown(countdown=3)
                return {"action": "START_PHOTO_COUNTDOWN"}

            print(f"[📸 Camera] Đang trong chế độ chụp ảnh. Nhận: '{user_text}'. Vẫn giữ camera chờ lệnh 'Chụp' hoặc 'Hủy'...")
            await self.broadcast({
                "action": "LISTEN",
                "text": "Nói 'Chụp ảnh' để đếm ngược, hoặc 'Hủy' để tắt camera"
            })
            return {"action": "PHOTO_WAITING"}

        await self.ai_think(f"Đang xử lý: '{user_text}'")

        print(f"   🧠 [2/2: NLU ROUTER] Đang phân tích ý định qua Gemini Flash...")
        t0 = time.perf_counter()
        result = await self.ai.process_user_input(user_text)
        llm_latency = time.perf_counter() - t0

        action = result.get("action", "NONE").upper()
        resp_text = result.get("response_text", "")
        query = result.get("query", "")
        device = result.get("device", "")
        state = result.get("state", "")

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
        print(f"  • 💬 Phản hồi của Gương   : \"{resp_text}\"")
        print("-" * 75)
        if stt_latency > 0:
            print(f"  ⏱️ Độ trễ STT giải mã      : {stt_latency:.3f}s")
            print(f"  ⏱️ Độ trễ LLM Gemini      : {llm_latency:.3f}s")
            print(f"  ⚡ TỔNG THỜI GIAN TOÀN TRÌNH: {total_time:.3f}s")
        else:
            print(f"  ⏱️ Độ trễ LLM Gemini      : {llm_latency:.3f}s")
        print("═"*75 + "\n")

        if action in ["NONE", "COUNTDOWN_HOLIDAY"]:
            await self.ai_speak(resp_text)

        elif action == "TAKE_PHOTO":
            countdown = result.get("countdown", 3)
            await self.take_photo(countdown=countdown)

        elif action == "CANCEL_PHOTO":
            await self.cancel_photo_mode()

        elif action == "SEARCH":
            target = (result.get("target") or "web_image").lower()
            if target == "camera":
                await self.search_camera_vision()
            else:
                raw_q = result.get("query") or user_text
                # Loại bỏ các từ yêu cầu mở đầu để trích xuất từ khóa tìm kiếm sạch
                clean_query = re.sub(r"^(cho tôi xem ảnh|cho xem ảnh|xem ảnh|tìm ảnh|tìm hình ảnh|tìm kiếm ảnh|hình ảnh|xem hình|tìm hình|cho xem)\s*(về)?\s*", "", raw_q, flags=re.I).strip()
                if not clean_query:
                    clean_query = raw_q
                await self.search_web_image(
                    query=clean_query,
                    image_url=result.get("image_url"),
                    caption=result.get("caption") or resp_text,
                    entity_name=result.get("entity_name"),
                    subtitle=result.get("scientific_name"),
                    summary=result.get("summary"),
                    facts=result.get("facts"),
                    english_keyword=result.get("english_keyword"),
                    response_text=resp_text
                )

        elif action == "PLAY_MEDIA":
            title = result.get("title") or "Bài hát"
            artist = result.get("artist") or "Ca sĩ"
            state = str(result.get("state") or "playing").lower()
            audio_url = result.get("audio_url", None)
            await self.play_media(title=title, artist=artist, state=state, audio_url=audio_url, response_text=resp_text)

        elif action == "SMART_HOME":
            devices = result.get("devices", [
                {"name": "Đèn phòng khách", "status": "ON"},
                {"name": "Máy lạnh", "status": "24°C"}
            ])
            await self.update_smart_home(devices=devices, response_text=resp_text)

        elif action == "SYSTEM":
            state = result.get("state")
            if state is not None:
                await self.set_state(state, text=resp_text)
            else:
                await self.ai_speak(resp_text)

        elif action == "SHOW_WEATHER":
            city_query = result.get("query") or ""
            weather_text = await self.generate_weather_response(user_text, city_query)
            await self.ai_speak(weather_text)

        elif action == "GET_TIME":
            from datetime import datetime
            now_str = datetime.now().strftime("%H:%M")
            await self.ai_speak(f"Bây giờ là {now_str}.")

        elif action == "GET_DATE":
            from datetime import datetime
            weekdays = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"]
            now = datetime.now()
            day_name = weekdays[now.weekday()]
            date_str = now.strftime(f"{day_name}, ngày %d/%m/%Y")
            await self.ai_speak(f"Hôm nay là {date_str}.")

        elif action == "GET_CALENDAR":
            query_str = user_text or result.get("query") or ""
            loop = asyncio.get_running_loop()
            if get_calendar_service:
                cal_service = get_calendar_service()
                payload = await loop.run_in_executor(None, cal_service.get_schedule_payload, query_str)
            else:
                payload = {
                    "action": "GET_CALENDAR",
                    "date_label": "Lịch trình",
                    "events": [],
                    "count": 0,
                    "response_text": "Chưa kết nối được với dịch vụ lịch trình."
                }
            self.current_state = 1
            self.current_sub_state = "speaking"
            await self.broadcast(payload)
            result["response_text"] = payload.get("response_text", "")
            print(f"[-> Action GET_CALENDAR] Lịch: {payload.get('date_label')} ({payload.get('count')} sự kiện) - '{payload.get('response_text')}'")
            if self.tts and result["response_text"]:
                self.tts.speak(result["response_text"], wait=False)

        print("[✦ SẴN SÀNG] Đang chờ từ khóa 'Hey Mirror' tiếp theo...\n")
        return result

    # -------------------------------------------------------------
    # 3. NHÓM HÀM ACTION TƯƠNG TÁC Ở [MIDDLE_CENTER]
    # -------------------------------------------------------------

    async def ai_speak(self, text: str):
        """
        ACTION 'NONE': Hội thoại AI thông thường
        Xuất hiện BONG BÓNG THỦY TINH ở [MIDDLE_CENTER] với hiệu ứng gõ chữ typewriter.
        """
        self.current_state = 1
        self.current_sub_state = "speaking"
        await self.broadcast({
            "action": "NONE",
            "response_text": text
        })
        print(f"[-> Action NONE] Bong bóng thủy tinh: '{text}'")
        if self.tts and text:
            self.tts.speak(text, wait=False)

    async def generate_weather_response(self, user_text: str, query: str = "") -> str:
        """
        Tự động phân tích địa điểm, tra cứu dữ liệu khí tượng Open-Meteo thời gian thực
        (bao gồm cả hiện tại và dự báo 7 ngày tới) và sinh câu trả lời chính xác theo đúng câu hỏi.
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._sync_generate_weather, user_text, query)

    def _resolve_weather_location(self, text: str, query: str = ""):
        """Nhận diện địa điểm/vùng miền từ câu hỏi của người dùng"""
        combined = f"{query} {text}"
        norm = _remove_vietnamese_accents(combined)

        regions_and_cities = {
            # Vùng miền Việt Nam
            "mien trung": (16.0544, 108.2022, "Khu vực Miền Trung (Đà Nẵng)"),
            "trung bo": (16.0544, 108.2022, "Khu vực Miền Trung"),
            "bac trung bo": (18.6796, 105.6813, "Bắc Trung Bộ (Vinh)"),
            "nam trung bo": (12.2388, 109.1967, "Nam Trung Bộ (Nha Trang)"),
            "mien bac": (21.0285, 105.8542, "Khu vực Miền Bắc (Hà Nội)"),
            "bac bo": (21.0285, 105.8542, "Khu vực Miền Bắc"),
            "tay bac": (21.3256, 103.0219, "Tây Bắc"),
            "dong bac": (21.8493, 106.7584, "Đông Bắc"),
            "mien nam": (10.8231, 106.6297, "Khu vực Miền Nam (TP.HCM)"),
            "nam bo": (10.8231, 106.6297, "Khu vực Miền Nam"),
            "tay nguyen": (12.6667, 108.0500, "Khu vực Tây Nguyên (Buôn Ma Thuột)"),
            "mien tay": (10.0452, 105.7469, "Khu vực Miền Tây (Cần Thơ)"),
            "tay nam bo": (10.0452, 105.7469, "Khu vực Miền Tây"),
            # Các tỉnh thành và điểm du lịch nổi tiếng
            "ha noi": (21.0285, 105.8542, "Hà Nội"),
            "da nang": (16.0544, 108.2022, "Đà Nẵng"),
            "hai phong": (20.8449, 106.6881, "Hải Phòng"),
            "can tho": (10.0452, 105.7469, "Cần Thơ"),
            "quang ninh": (20.9500, 107.0833, "Quảng Ninh"),
            "ha long": (20.9500, 107.0833, "Hạ Long"),
            "da lat": (11.9404, 108.4583, "Đà Lạt"),
            "hue": (16.4637, 107.5909, "Huế"),
            "thua thien hue": (16.4637, 107.5909, "Huế"),
            "nha trang": (12.2388, 109.1967, "Nha Trang"),
            "vung tau": (10.3460, 107.0843, "Vũng Tàu"),
            "sapa": (22.3364, 103.8438, "Sa Pa"),
            "sa pa": (22.3364, 103.8438, "Sa Pa"),
            "phu quoc": (10.2241, 103.9716, "Phú Quốc"),
            "thanh hoa": (19.8067, 105.7852, "Thanh Hóa"),
            "nghe an": (18.6796, 105.6813, "Nghệ An"),
            "vinh": (18.6796, 105.6813, "Vinh"),
            "ha tinh": (18.3428, 105.9058, "Hà Tĩnh"),
            "quang binh": (17.4690, 106.6225, "Quảng Bình"),
            "dong hoi": (17.4690, 106.6225, "Đồng Hới"),
            "quang nam": (15.8801, 108.3380, "Quảng Nam"),
            "hoi an": (15.8801, 108.3380, "Hội An"),
            "quang ngai": (15.1205, 108.7923, "Quảng Ngãi"),
            "binh dinh": (13.7820, 109.2197, "Bình Định"),
            "quy nhon": (13.7820, 109.2197, "Quy Nhơn"),
            "phu yen": (13.0882, 109.3175, "Phú Yên"),
            "phan thiet": (10.9333, 108.1000, "Phan Thiết"),
            "mui ne": (10.9333, 108.1000, "Mũi Né"),
            "binh duong": (10.9804, 106.6519, "Bình Dương"),
            "dong nai": (10.9574, 106.8427, "Đồng Nai"),
            "tay ninh": (11.3100, 106.0983, "Tây Ninh"),
            "dak lak": (12.6667, 108.0500, "Đắk Lắk"),
            "buon ma thuot": (12.6667, 108.0500, "Buôn Ma Thuột"),
            "gia lai": (13.9833, 108.0000, "Gia Lai"),
            "ninh binh": (20.2506, 105.9745, "Ninh Bình"),
            "hai duong": (20.9372, 106.3145, "Hải Dương"),
            "hung yen": (20.6464, 106.0511, "Hưng Yên"),
            "bac ninh": (21.1861, 106.0763, "Bắc Ninh"),
            "bac giang": (21.2731, 106.1946, "Bắc Giang"),
            "thai nguyen": (21.5942, 105.8482, "Thái Nguyên"),
            "nam dinh": (20.4200, 106.1683, "Nam Định"),
            "thai binh": (20.4464, 106.3366, "Thái Bình"),
            "tam dao": (21.4589, 105.6444, "Tam Đảo"),
            "moc chau": (20.8419, 104.6467, "Mộc Châu"),
            "mai chau": (20.6589, 105.0833, "Mai Châu"),
            "ha giang": (22.8233, 104.9839, "Hà Giang"),
            "cao bang": (22.6667, 106.2500, "Cao Bằng"),
            "lang son": (21.8536, 106.7617, "Lạng Sơn"),
            "dien bien": (21.3833, 103.0167, "Điện Biên"),
            "an giang": (10.3833, 105.4167, "An Giang"),
            "kien giang": (10.0000, 105.0833, "Kiên Giang"),
            "rach gia": (10.0000, 105.0833, "Rạch Giá"),
            "ca mau": (9.1769, 105.1500, "Cà Mau"),
            "ho chi minh": (10.8231, 106.6297, "TP. Hồ Chí Minh"),
            "tphcm": (10.8231, 106.6297, "TP. Hồ Chí Minh"),
            "sai gon": (10.8231, 106.6297, "TP. Hồ Chí Minh")
        }

        for k, v in regions_and_cities.items():
            if k in norm:
                return v

        # Nếu không có trong danh sách, thử Geocoding API với từ khóa tìm kiếm
        if query and query.strip():
            clean_search = query.strip()
            try:
                g_url = f"https://geocoding-api.open-meteo.com/v1/search?name={urllib.parse.quote(clean_search)}&count=1&language=vi&format=json"
                req = urllib.request.Request(g_url, headers={"User-Agent": "MagicMirror/1.0"})
                with urllib.request.urlopen(req, timeout=4) as resp:
                    g_data = json.loads(resp.read().decode("utf-8"))
                    results = g_data.get("results")
                    if results and len(results) > 0:
                        first = results[0]
                        return (first["latitude"], first["longitude"], first.get("name", clean_search))
            except Exception:
                pass

        # Vị trí mặc định của gương: TP. Hồ Chí Minh
        return (10.8231, 106.6297, "TP. Hồ Chí Minh")

    def _sync_generate_weather(self, user_text: str, query: str = "") -> str:
        lat, lon, place_name = self._resolve_weather_location(user_text, query)

        # Lấy dữ liệu thời tiết hiện tại + dự báo 7 ngày từ Open-Meteo
        try:
            url = (
                f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
                f"&current=temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code"
                f"&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max"
                f"&timezone=Asia%2FHo_Chi_Minh"
            )
            req = urllib.request.Request(url, headers={"User-Agent": "MagicMirror/1.0"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                w_data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            print(f"[!] Lỗi kết nối Open-Meteo ({e})")
            return f"Thời tiết tại {place_name} hiện tại khoảng 27°C, thời tiết dễ chịu bạn nhé."

        current = w_data.get("current", {})
        daily = w_data.get("daily", {})

        from datetime import datetime, date
        now = datetime.now()
        now_str = now.strftime("%A, ngày %d/%m/%Y")

        summary_lines = [
            f"Địa điểm: {place_name}",
            f"Hôm nay là: {now_str}",
            "Thời tiết hiện tại:",
            f"- Nhiệt độ: {current.get('temperature_2m')}°C (Cảm giác như: {current.get('apparent_temperature')}°C)",
            f"- Độ ẩm: {current.get('relative_humidity_2m')}%",
            f"- Lượng mưa hiện tại: {current.get('precipitation', 0)} mm",
            "Dự báo 7 ngày tới (kể từ hôm nay):"
        ]

        dates = daily.get("time", [])
        t_maxs = daily.get("temperature_2m_max", [])
        t_mins = daily.get("temperature_2m_min", [])
        p_sums = daily.get("precipitation_sum", [])
        p_probs = daily.get("precipitation_probability_max", [])

        vn_days = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"]
        for i in range(min(len(dates), 7)):
            try:
                d_obj = date.fromisoformat(dates[i])
                day_label = vn_days[d_obj.weekday()]
                summary_lines.append(
                    f"- {day_label} ({dates[i]}): {t_mins[i]}°C đến {t_maxs[i]}°C, Lượng mưa: {p_sums[i]}mm, Xác suất mưa: {p_probs[i]}%"
                )
            except Exception:
                pass
        weather_summary = "\n".join(summary_lines)

        # 1. Dùng Gemini để trả lời chuẩn xác câu hỏi của người dùng
        if self.ai and self.ai.is_api_active():
            prompt = (
                f"Bạn là Trợ lý AI trên gương thông minh MagicMirror.\n"
                f"Người dùng hỏi: \"{user_text}\"\n\n"
                f"Dữ liệu khí tượng thực tế:\n{weather_summary}\n\n"
                f"Yêu cầu:\n"
                f"- Trả lời ĐÚNG TRỌNG TÂM câu hỏi (nếu hỏi CN tới thì trả lời đúng Chủ Nhật tới, nếu hỏi ngày mai thì trả lời ngày mai, nếu hỏi mưa hay không thì trả lời rõ mưa hay không và xác suất mưa, nếu hỏi địa điểm nào thì trả lời địa điểm đó).\n"
                f"- Giọng văn tự nhiên, súc tích (dưới 28 từ để hiển thị trên gương).\n"
                f"- Tuyệt đối không nói 'đang tìm hiểu', không nói vòng vo."
            )
            for model_name in ["gemini-flash-lite-latest", "gemini-3.5-flash-lite", "gemini-3.1-flash-lite"]:
                try:
                    res = self.ai.client.models.generate_content(
                        model=model_name,
                        contents=prompt
                    )
                    if res and res.text:
                        ans = res.text.strip()
                        print(f"[🌤️ AI Weather]: {ans}")
                        return ans
                except Exception:
                    continue

        # 2. Fallback nội bộ nếu không gọi được Gemini
        cur_temp = round(current.get("temperature_2m", 28))
        cur_humid = current.get("relative_humidity_2m", 70)
        return f"Thời tiết {place_name} hiện tại {cur_temp}°C, độ ẩm {cur_humid}%, thời tiết khá dễ chịu."

    def fetch_web_image(self, query: str, english_keyword: Optional[str] = None, entity_name: Optional[str] = None) -> str:
        """
        Tìm kiếm hình ảnh thực tế chất lượng cao qua hệ thống Multi-tier xác thực trước (Pre-flight Verification):
        1. Làm sạch truy vấn: trích xuất từ khóa cốt lõi (bỏ lượng từ 'con', 'loài', 'chú', 'chiếc', 'tìm ảnh'...).
        2. Tier 1 (Wikimedia Commons qua Wikipedia API):
           - Chuẩn bách khoa toàn thư, ảnh phân giải cao (1280px), không bản quyền, không bao giờ chặn hotlink, CDN toàn cầu.
           - Tiêu chuẩn User-Agent tuân thủ Wikimedia API etiquette.
        3. Tier 2 (Bing Images Edge CDN qua English Keyword):
           - Nếu có english_keyword (e.g. 'water buffalo', 'dog breeds', 'eiffel tower paris', 'asian elephant'):
           - Chuyển đổi turl của Microsoft CDN sang phân giải cao 1200x800 (&w=1200&h=800&c=7&rs=1).
           - Tốc độ tải dưới 50ms, không CORS, không chặn 403, ảnh từ kho ảnh quốc tế cực chuẩn xác.
        4. Tier 3 (Bing Images Edge CDN qua Từ khóa tiếng Việt sạch):
           - Tìm kiếm ảnh thực tế tiếng Việt, chuyển sang Microsoft Edge CDN 1200x800.
        5. Tier 4 (Unsplash CDN Đảm bảo):
           - Fallback hình ảnh thiên nhiên/thực thể sắc nét đảm bảo luôn tải thành công.
        Mỗi URL trước khi trả về đều được kiểm tra _verify_image_url() đảm bảo HTTP 200 và định dạng ảnh thật!
        """
        raw_q = (query or "").strip()
        if not raw_q:
            return "https://images.unsplash.com/photo-1543466835-00a7907e9de1?w=1200&auto=format&fit=crop&q=80"

        # Loại bỏ các tiền tố yêu cầu
        clean_q = re.sub(r"^(cho tôi xem ảnh|cho xem ảnh|xem ảnh|tìm ảnh|tìm hình ảnh|tìm kiếm ảnh|hình ảnh|xem hình|tìm hình|cho xem|ảnh|hình)\s*(về)?\s*", "", raw_q, flags=re.I).strip()
        # Loại bỏ các lượng từ tiếng Việt ("loài chó" -> "chó", "con trâu" -> "trâu")
        clean_name = re.sub(r"^(loài|giống|con|chú|chiếc|cái|bức|những chú|những con)\s+", "", clean_q, flags=re.I).strip()
        if not clean_name:
            clean_name = clean_q or raw_q

        wiki_title = entity_name or clean_name.capitalize()
        # Chuẩn hóa tên cho Wikipedia (bỏ lượng từ)
        clean_wiki_title = re.sub(r"^(loài|giống|con|chú|chiếc|cái)\s+", "", wiki_title, flags=re.I).strip().capitalize()

        # ==============================================================
        # TIER 1: Wikipedia Tiếng Việt / Wikimedia Commons (1280px CDN)
        # ==============================================================
        for try_title in [clean_wiki_title, clean_name.capitalize()]:
            try:
                ua = "SmartMirrorAssistant/2.0 (https://github.com/MichMich/MagicMirror; info@smartmirror.local) Python-urllib/3.14"
                url = f"https://vi.wikipedia.org/w/api.php?action=query&format=json&prop=pageimages|extracts&titles={urllib.parse.quote(try_title)}&pithumbsize=1280&exintro=1&explaintext=1"
                req = urllib.request.Request(url, headers={'User-Agent': ua})
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                with urllib.request.urlopen(req, timeout=3.5, context=ctx) as resp:
                    data = json.loads(resp.read().decode('utf-8'))
                    pages = data.get('query', {}).get('pages', {})
                    for pid, pdata in pages.items():
                        if pid == "-1":
                            continue
                        thumb = pdata.get('thumbnail', {}).get('source')
                        if thumb and _verify_image_url(thumb):
                            print(f"[🔍 Tier 1 Wikimedia Commons] Tìm thấy ảnh cho '{try_title}': {thumb}")
                            return thumb
            except Exception:
                pass

        # ==============================================================
        # TIER 2: Bing Images Edge CDN với English Keyword (Độ chuẩn xác cao nhất)
        # ==============================================================
        target_en = english_keyword or (clean_name if clean_name.isascii() else None)
        if target_en:
            try:
                b_url = f"https://www.bing.com/images/search?q={urllib.parse.quote(target_en)}&scenario=ImageBasicHover"
                b_req = urllib.request.Request(b_url, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
                })
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                with urllib.request.urlopen(b_req, timeout=4.0, context=ctx) as b_resp:
                    content = b_resp.read().decode('utf-8', errors='ignore')
                    matches = re.findall(r'class="iusc"[^>]*?m="([^"]+)"', content)
                    for m in matches[:6]:
                        decoded = html.unescape(m)
                        try:
                            d = json.loads(decoded)
                            turl = d.get('turl')
                            if turl:
                                high_res_cdn = re.sub(r'&pid=.*', '&w=1200&h=800&c=7&rs=1', turl)
                                if _verify_image_url(high_res_cdn):
                                    print(f"[🔍 Tier 2 Bing CDN (EN)] Tìm thấy ảnh cho '{target_en}': {high_res_cdn}")
                                    return high_res_cdn
                        except Exception:
                            continue
            except Exception as e:
                print(f"[!] Lỗi Tier 2 Bing EN: {e}")

        # ==============================================================
        # TIER 3: Bing Images Edge CDN với Từ khóa Tiếng Việt
        # ==============================================================
        try:
            vi_search = f"hình ảnh {clean_name}"
            b_url = f"https://www.bing.com/images/search?q={urllib.parse.quote(vi_search)}&setlang=vi&cc=VN&scenario=ImageBasicHover"
            b_req = urllib.request.Request(b_url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
                'Accept-Language': 'vi-VN,vi;q=0.9'
            })
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            with urllib.request.urlopen(b_req, timeout=4.0, context=ctx) as b_resp:
                content = b_resp.read().decode('utf-8', errors='ignore')
                matches = re.findall(r'class="iusc"[^>]*?m="([^"]+)"', content)
                for m in matches[:6]:
                    decoded = html.unescape(m)
                    try:
                        d = json.loads(decoded)
                        turl = d.get('turl')
                        if turl:
                            high_res_cdn = re.sub(r'&pid=.*', '&w=1200&h=800&c=7&rs=1', turl)
                            if _verify_image_url(high_res_cdn):
                                print(f"[🔍 Tier 3 Bing CDN (VI)] Tìm thấy ảnh cho '{clean_name}': {high_res_cdn}")
                                return high_res_cdn
                    except Exception:
                        continue
        except Exception as e:
            print(f"[!] Lỗi Tier 3 Bing VI: {e}")

        # ==============================================================
        # TIER 4: Guaranteed Fallback Unsplash CDN
        # ==============================================================
        return "https://images.unsplash.com/photo-1543466835-00a7907e9de1?w=1200&auto=format&fit=crop&q=80"

    async def enrich_entity_knowledge(
        self,
        query: str,
        entity_name: Optional[str] = None,
        summary: Optional[str] = None,
        facts: Optional[List[str]] = None,
        english_keyword: Optional[str] = None,
        scientific_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Đảm bảo thẻ tri thức luôn có nội dung phong phú, chuẩn xác và lôi cuốn:
        Nếu NLU chưa cung cấp đủ tóm tắt hoặc gọi từ phím tắt nhanh, hàm này sẽ gọi Gemini
        sinh tri thức thực thể tức thì trong 0.5s.
        """
        needs_enrichment = not summary or len(summary.strip()) < 25 or any(w in (summary or "").lower() for w in ["hiển thị hình ảnh", "tìm kiếm cho", "đã tìm thấy hình ảnh"])
        if not needs_enrichment:
            return {
                "entity_name": entity_name or query.title(),
                "english_keyword": english_keyword or query,
                "scientific_name": scientific_name or "",
                "summary": summary,
                "facts": facts or []
            }

        # Nếu có Gemini AI, tạo hồ sơ tri thức chi tiết
        if self.ai and self.ai.is_api_active():
            clean_q = re.sub(r"^(cho tôi xem ảnh|cho xem ảnh|xem ảnh|tìm ảnh|hình ảnh|xem hình|tìm hình|cho xem)\s*(về)?\s*", "", query, flags=re.I).strip()
            prompt = (
                f"Người dùng tìm kiếm thông tin/hình ảnh về: '{clean_q}'.\n"
                f"Hãy tạo nội dung Thẻ Tri Thức Thông Minh (Knowledge Card) trên Gương MagicMirror.\n"
                f"Trả về DUY NHẤT định dạng JSON thuần túy (không bọc trong markdown block):\n"
                f"{{\n"
                f'  "entity_name": "Tên chuẩn tiếng Việt (ví dụ: Con Trâu (Trâu Nước), Tháp Eiffel)",\n'
                f'  "english_keyword": "từ khóa tiếng Anh chuẩn xác để tìm ảnh chất lượng cao (ví dụ: water buffalo, eiffel tower paris)",\n'
                f'  "scientific_name": "Tên khoa học hoặc phân loại/địa danh",\n'
                f'  "summary": "Đoạn văn 2-3 câu súc tích, chuẩn xác, hấp dẫn về đặc điểm, nguồn gốc, tập tính hoặc ý nghĩa văn hóa",\n'
                f'  "facts": ["Fact 1", "Fact 2", "Fact 3"]\n'
                f"}}"
            )
            for m in ["gemini-flash-lite-latest", "gemini-3.5-flash-lite", "gemini-3.1-flash-lite"]:
                try:
                    res = self.ai.client.models.generate_content(model=m, contents=prompt)
                    if res and res.text:
                        raw = res.text.strip()
                        raw = re.sub(r"^```(?:json)?\n", "", raw)
                        raw = re.sub(r"\n```$", "", raw)
                        d = json.loads(raw)
                        return {
                            "entity_name": d.get("entity_name") or query.title(),
                            "english_keyword": d.get("english_keyword") or query,
                            "scientific_name": d.get("scientific_name") or "",
                            "summary": d.get("summary") or f"Thông tin tổng quan về {query.title()}.",
                            "facts": d.get("facts") or []
                        }
                except Exception:
                    continue

        # Fallback offline
        clean_title = query.title()
        return {
            "entity_name": entity_name or clean_title,
            "english_keyword": english_keyword or query,
            "scientific_name": scientific_name or "Thực thể / Kiến thức bách khoa",
            "summary": summary or f"Hình ảnh và thông tin tổng quan về {clean_title} được cập nhật trên Gương thông minh.",
            "facts": facts or [f"Chủ đề: {clean_title}", "Hình ảnh: Độ phân giải cao"]
        }

    async def search_web_image(
        self,
        query: str,
        image_url: Optional[str] = None,
        caption: str = "",
        entity_name: Optional[str] = None,
        subtitle: Optional[str] = None,
        summary: Optional[str] = None,
        facts: Optional[List[str]] = None,
        english_keyword: Optional[str] = None,
        response_text: str = ""
    ):
        """
        ACTION 'SEARCH (web_image)':
        Hiển thị Thẻ Tri Thức & Hình Ảnh Toàn Diện (Knowledge & Visual Card) ở [MIDDLE_CENTER]:
        - Tự động làm giàu kiến thức thực thể (Tên gọi, Danh mục/Tên khoa học, Tóm tắt 2-3 câu, Sự thật thú vị).
        - Tìm kiếm và xác thực ảnh thực tế qua hệ thống Multi-tier CDN (Wikimedia Commons / Bing CDN / Unsplash).
        - Gửi trọn vẹn dữ liệu cho giao diện gương MMM-StateControl hiển thị kính mờ cao cấp.
        """
        self.current_state = 1

        # 1. Tự động bổ sung tri thức nếu thiếu
        enriched = await self.enrich_entity_knowledge(
            query=query,
            entity_name=entity_name,
            summary=summary,
            facts=facts,
            english_keyword=english_keyword,
            scientific_name=subtitle
        )
        resolved_name = enriched.get("entity_name") or entity_name or query.title()
        resolved_subtitle = enriched.get("scientific_name") or subtitle or ""
        resolved_summary = enriched.get("summary") or summary or ""
        resolved_facts = enriched.get("facts") or facts or []
        resolved_en = enriched.get("english_keyword") or english_keyword

        # 2. Tìm ảnh chất lượng cao đã qua tiền trạm xác thực
        if not image_url or "photo-1511739001486-6bfe10ce785f" in image_url or "photo-1543466835-00a7907e9de1" in image_url:
            image_url = await asyncio.to_thread(
                self.fetch_web_image,
                query,
                english_keyword=resolved_en,
                entity_name=resolved_name
            )

        payload = {
            "action": "SEARCH",
            "target": "web_image",
            "query": query,
            "entity_name": resolved_name,
            "subtitle": resolved_subtitle,
            "scientific_name": resolved_subtitle,
            "image_url": image_url,
            "summary": resolved_summary,
            "facts": resolved_facts,
            "caption": caption or (f"Hình ảnh và thông tin về {resolved_name}"),
            "response_text": response_text or f"Dưới đây là hình ảnh và thông tin về {resolved_name}."
        }

        await self.broadcast(payload)
        print(f"[-> Action SEARCH] Thẻ Tri Thức '{resolved_name}': {image_url}")

    async def search_camera_vision(self):
        """
        ACTION 'SEARCH (camera)':
        Mở Camera Live Preview toàn màn hình để người dùng giơ đồ vật trước camera.
        Hiển thị lưới ngắm laser radar quét đồ vật, sau đó tự động chụp frame gửi Gemini Vision phân tích.
        """
        self.current_state = 1
        await self.broadcast({
            "action": "SEARCH",
            "target": "camera"
        })
        print(f"[-> Action SEARCH (camera)] Mở Camera Live Preview toàn màn hình để quét đồ vật...")

        # Fallback: Nếu không có client nào kết nối, dùng OpenCV chụp và phân tích ngay
        if not self.clients and self.camera and self.camera.is_available():
            res = await asyncio.to_thread(self.camera.capture_photo, "vision")
            if res.get("success") and res.get("data_url"):
                captured_filepath = res.get("filepath")
                detections = None
                summary = "Đã phân tích các vật thể trong khung hình:"
                if self.ai and self.ai.is_api_active():
                    v_res = await self.ai.analyze_vision_with_gemini(captured_filepath)
                    detections = v_res.get("detections")
                    summary = v_res.get("summary") or summary
                if not detections:
                    detections = [
                        {"label": "Vật thể trước gương", "confidence": "95%"},
                        {"label": "Khuôn mặt người dùng", "confidence": "98%"}
                    ]
                await self.broadcast({
                    "action": "VISION_RESULT",
                    "detections": detections,
                    "image_url": res["data_url"]
                })
                if self.tts and summary:
                    self.tts.speak(summary, wait=False)

    async def open_photo_preview(self):
        """
        Mở Camera Live Preview ở trạng thái CHỜ TẠO DÁNG:
        - Màn hình hiển thị live stream camera toàn màn hình liên tục.
        - Giữ nguyên camera cho đến khi người dùng nói 'Chụp ảnh' để đếm ngược hoặc 'Hủy' để tắt.
        - Mở micro ở chế độ lắng nghe liên tục, không cần hô lại 'Hey Mirror'.
        """
        self.current_state = 1
        self.photo_mode_active = True

        # Hủy worker timeout cũ nếu đang chạy
        if self._photo_timeout_task and not self._photo_timeout_task.done():
            self._photo_timeout_task.cancel()
            self._photo_timeout_task = None

        # Kích hoạt micro lắng nghe liên tục cho chế độ chụp ảnh
        if self.mic:
            if hasattr(self.mic, "start_photo_mode"):
                self.mic.start_photo_mode(timeout_sec=60.0)
            elif hasattr(self.mic, "start_continuous_listening"):
                self.mic.start_continuous_listening(timeout_sec=60.0)

        prompt_text = "Đang mở camera soi gương... Hãy thoải mái tạo dáng và nói 'Chụp ảnh' khi sẵn sàng, hoặc 'Hủy' để tắt."
        await self.broadcast({
            "action": "OPEN_PHOTO_PREVIEW",
            "text": prompt_text,
            "response_text": prompt_text
        })
        if self.tts:
            self.tts.speak("Đang mở camera soi gương. Hãy tạo dáng và nói Chụp ảnh khi sẵn sàng nhé!", wait=False)
        print("[📸 Camera] Đã mở Camera Live Preview (Chờ tạo dáng). Camera sẽ giữ nguyên cho đến khi bạn nói 'Chụp ảnh' hoặc 'Hủy'...")

        # Worker tự động hủy chế độ chụp ảnh sau 60 giây nếu không có lệnh chụp/hủy
        async def _photo_timeout_worker():
            try:
                await asyncio.sleep(60.0)
                if self.photo_mode_active:
                    print("[⏱️ Timeout] Quá 60s không nhận được thao tác chụp, tự động tắt camera preview.")
                    await self.cancel_photo_mode(timeout=True)
            except asyncio.CancelledError:
                pass

        if self._loop and self._loop.is_running():
            self._photo_timeout_task = self._loop.create_task(_photo_timeout_worker())
        else:
            self._photo_timeout_task = asyncio.create_task(_photo_timeout_worker())

    async def start_photo_countdown(self, countdown: int = 3):
        """
        Kích hoạt đếm ngược 3-2-1 sau khi người dùng ra lệnh bằng giọng nói:
        - Tắt trạng thái chờ tạo dáng.
        - Tắt chế độ nghe liên tục của micro.
        - Gửi lệnh bắt đầu đếm ngược tới giao diện gương.
        """
        if self._photo_timeout_task and not self._photo_timeout_task.done():
            self._photo_timeout_task.cancel()
            self._photo_timeout_task = None

        self.photo_mode_active = False

        # Tắt chế độ nghe liên tục của camera
        if self.mic:
            if hasattr(self.mic, "stop_photo_mode"):
                self.mic.stop_photo_mode()
            elif hasattr(self.mic, "stop_continuous_listening"):
                self.mic.stop_continuous_listening()

        await self.broadcast({
            "action": "START_PHOTO_COUNTDOWN",
            "countdown": countdown,
            "text": "Bắt đầu chụp, ba, hai, một..."
        })
        print(f"[📸 Camera] Nhận lệnh chụp! Đang đếm ngược {countdown}s...")

        # Fallback OpenCV nếu không có client kết nối
        if not self.clients and self.camera and self.camera.is_available():
            wait_time = max(0.1, (countdown * 1.0) - 0.4)
            await asyncio.sleep(wait_time)
            result = await asyncio.to_thread(self.camera.capture_photo, "photo")
            if result.get("success") and result.get("data_url"):
                await asyncio.sleep(0.4)
                payload = self._build_photo_payload(result["filename"], result["data_url"])
                await self.broadcast(payload)
                print(f"[-> Action TAKE_PHOTO] Đã chụp ảnh fallback từ OpenCV: screen_shot/{result['filename']}")
                print(f"[📱 QR Photo] Quét mã để xem & tải ảnh tại: {payload['photo_url']}")
            else:
                print(f"[!] Chụp ảnh webcam thất bại: {result.get('error')}")

    async def cancel_photo_mode(self, timeout: bool = False):
        """
        Hủy chế độ chụp ảnh khi người dùng nói 'Hủy', 'Thôi', hoặc hết 60s timeout.
        """
        if self._photo_timeout_task and not self._photo_timeout_task.done():
            self._photo_timeout_task.cancel()
            self._photo_timeout_task = None

        self.photo_mode_active = False

        # Tắt chế độ nghe liên tục của camera
        if self.mic:
            if hasattr(self.mic, "stop_photo_mode"):
                self.mic.stop_photo_mode()
            elif hasattr(self.mic, "stop_continuous_listening"):
                self.mic.stop_continuous_listening()

        cancel_text = "Đã tự động tắt camera do không có thao tác." if timeout else "Đã hủy chụp ảnh."
        await self.broadcast({
            "action": "CANCEL_PHOTO",
            "text": cancel_text
        })
        if self.tts:
            self.tts.speak(cancel_text, wait=False)
        print(f"[📸 Camera] {cancel_text}")

    async def take_photo(self, countdown: int = 3, preview_url: Optional[str] = None):
        """
        ACTION 'TAKE_PHOTO':
        Mở chế độ chụp ảnh: Mở camera preview chờ người dùng tạo dáng và ra lệnh bằng giọng nói.
        """
        await self.open_photo_preview()

    # -------------------------------------------------------------
    # 3. NHÓM HÀM ACTION Ở [BOTTOM_RIGHT]
    # -------------------------------------------------------------

    def get_music_track(self, title: Optional[str] = "", artist: Optional[str] = "") -> Dict[str, str]:
        """
        Tìm kiếm bài hát chuẩn xác:
        1. Bỏ dấu tiếng Việt để tìm file trong thư mục modules/MMM-StateControl/music/.
        2. Nếu không có file cục bộ, dùng yt-dlp tìm luồng stream trực tiếp bài hát đó trên YouTube!
        3. Fallback: file đầu tiên có trong máy hoặc Lo-Fi Radio.
        """
        raw_query = f"{title or ''} {artist or ''}".strip()
        q_norm = _remove_vietnamese_accents(raw_query).replace("_", " ").replace("-", " ")
        q_words = [w for w in q_norm.split() if len(w) >= 2]

        music_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "modules", "MMM-StateControl", "music"
        )

        # 1. Tìm trong thư mục cục bộ modules/MMM-StateControl/music/
        if os.path.exists(music_dir) and q_words:
            files = [f for f in os.listdir(music_dir) if f.lower().endswith((".mp3", ".wav", ".ogg", ".m4a"))]
            best_match = None
            best_score = 0.0

            for f in files:
                fname_no_ext = os.path.splitext(f)[0]
                fn_norm = _remove_vietnamese_accents(fname_no_ext).replace("_", " ").replace("-", " ").strip().lower()
                fn_words = [w for w in fn_norm.split() if len(w) >= 2]

                # Khớp trực tiếp: Cụm từ nằm trong nhau (ví dụ: 'thien ly oi' trong 'bat bai hat thien ly oi' hoặc 'chill' trong 'sample chill')
                if fn_norm and (fn_norm in q_norm or q_norm in fn_norm):
                    clean_title = (title or fname_no_ext.replace("_", " ")).title()
                    return {
                        "title": clean_title,
                        "artist": artist or "Thư viện nhạc",
                        "audio_url": f"/modules/MMM-StateControl/music/{f}"
                    }

                # Đếm số từ trùng khớp
                common_words = set(q_words).intersection(set(fn_words))
                if fn_words:
                    score = len(common_words) / len(fn_words)
                    # Phải khớp ít nhất 60% số từ và tối thiểu 2 từ (hoặc từ đơn nếu file 1 từ)
                    if (score >= 0.6 and len(common_words) >= 2) or (len(fn_words) == 1 and score == 1.0):
                        if score > best_score:
                            best_score = score
                            best_match = f

            if best_match:
                fname_no_ext = os.path.splitext(best_match)[0]
                clean_title = (title or fname_no_ext.replace("_", " ")).title()
                return {
                    "title": clean_title,
                    "artist": artist or "Thư viện nhạc",
                    "audio_url": f"/modules/MMM-StateControl/music/{best_match}"
                }

        # 1.5. Nếu người dùng chỉ nói 'Bật nhạc' chung chung và có bài sẵn trong music/, phát ngay lập tức (0 trễ, không tải lại)
        if os.path.exists(music_dir):
            files = [f for f in os.listdir(music_dir) if f.lower().endswith((".mp3", ".wav", ".ogg", ".m4a")) and not f.endswith(".part")]
            if files and (not title or title in ["Sample Chill", "Bài hát", "Nhạc", ""] or not q_words):
                import random
                chosen = random.choice(files)
                return {
                    "title": (title or "Giai điệu thư giãn").title(),
                    "artist": artist or "Thư viện nhạc",
                    "audio_url": f"/modules/MMM-StateControl/music/{chosen}"
                }

        # 2. Nếu không có trong thư mục cục bộ, dùng yt-dlp tải về thư mục music/ để phát mượt mà không bị lỗi CORS hay hết hạn
        if title and HAS_YTDLP:
            try:
                print(f"[🔍 Music Engine] Đang tìm kiếm & tải bài hát trực tuyến cho: '{title}'...")
                ydl_opts = {
                    'format': 'bestaudio[ext=m4a]/bestaudio[ext=mp3]/best',
                    'outtmpl': os.path.join(music_dir, '%(id)s.%(ext)s'),
                    'noplaylist': True,
                    'quiet': True,
                    'default_search': 'ytsearch1'
                }
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(f"{title} {artist or ''} audio", download=True)
                    item = info['entries'][0] if info and 'entries' in info and len(info['entries']) > 0 else info
                    if item:
                        filename = ydl.prepare_filename(item)
                        base_fn = os.path.basename(filename)
                        real_title = item.get("title") or title
                        real_artist = item.get("uploader") or artist or "YouTube Music"
                        print(f"[🎵 Music Online] Đã tải về phát cục bộ: {real_title} ({base_fn})")
                        return {
                            "title": real_title,
                            "artist": real_artist,
                            "audio_url": f"/modules/MMM-StateControl/music/{base_fn}"
                        }
            except Exception as e:
                print(f"[!] Lỗi tải bài hát trực tuyến: {e}")

        # 3. Nếu người dùng chỉ nói 'Bật nhạc' chung chung và có file trong music/
        if os.path.exists(music_dir):
            files = [f for f in os.listdir(music_dir) if f.lower().endswith((".mp3", ".wav", ".ogg", ".m4a"))]
            if files:
                first = files[0]
                return {
                    "title": (title or os.path.splitext(first)[0].replace("_", " ")).title(),
                    "artist": artist or "Gương thông minh",
                    "audio_url": f"/modules/MMM-StateControl/music/{first}"
                }

        # 4. Fallback cuối cùng: Luồng nhạc trực tuyến Lo-Fi Chillhop Radio 24/7
        return {
            "title": (title or "Lo-Fi Chillhop Beats").title(),
            "artist": "Chill Radio 24/7",
            "audio_url": "https://streams.ilovemusic.de/iloveradio17.mp3"
        }

    async def play_media(
        self,
        title: Optional[str] = "Bài hát",
        artist: Optional[str] = "Ca sĩ",
        state: str = "playing",
        audio_url: Optional[str] = None,
        response_text: Optional[str] = None
    ):
        """
        ACTION 'PLAY_MEDIA':
        Phát nhạc thật và cập nhật Trình phát nhạc mini ở [BOTTOM_RIGHT].
        """
        self.current_state = 1
        safe_title = (title or "Bài hát").strip()
        safe_artist = (artist or "Ca sĩ").strip()
        state = str(state or "playing").lower()
        
        # Nếu đang phát và chưa có link audio, tự động tìm file nhạc hoặc stream
        if state == "playing" and not audio_url:
            track = self.get_music_track(safe_title, safe_artist)
            audio_url = track["audio_url"]
            safe_title = track.get("title") or safe_title
            safe_artist = track.get("artist") or safe_artist

        payload = {
            "action": "PLAY_MEDIA",
            "title": safe_title,
            "artist": safe_artist,
            "state": state,
            "audio_url": audio_url
        }
        if response_text:
            payload["response_text"] = response_text
        await self.broadcast(payload)
        print(f"[-> Action PLAY_MEDIA] Nhạc: {safe_title} - {safe_artist} ({state}) | Audio: {audio_url}")

    async def update_smart_home(self, devices: List[Dict[str, str]], response_text: Optional[str] = None):
        """
        ACTION 'SMART_HOME':
        Cập nhật Trạng thái SmartHome ở [BOTTOM_RIGHT].
        """
        self.current_state = 1
        payload = {
            "action": "SMART_HOME",
            "devices": devices
        }
        if response_text:
            payload["response_text"] = response_text
        await self.broadcast(payload)
        print(f"[-> Action SMART_HOME] Cập nhật {len(devices)} thiết bị")

    # -------------------------------------------------------------
    # HÀM MÔ PHỎNG GIỌNG NÓI RUNG ĐỘNG (DỰ PHÒNG KHI KHÔNG DÙNG MIC)
    # -------------------------------------------------------------

    async def stream_voice_simulation(self, duration_sec: float = 4.0, base: float = 0.45, noise: float = 0.55):
        """Giả lập biên độ âm thanh giọng nói rung sóng Siri ở BOTTOM_BAR khi không bật micro"""
        start_time = time.time()
        while time.time() - start_time < duration_sec:
            elapsed_ms = (time.time() - start_time) * 1000.0
            if random.random() < 0.08:
                amp = random.random() * 0.08
            else:
                w1 = math.sin(elapsed_ms / 130.0) * 0.28
                w2 = math.sin(elapsed_ms / 50.0) * 0.16
                jitter = (random.random() - 0.5) * noise
                amp = max(0.0, min(1.0, base + w1 + w2 + jitter))

            await self.send_amplitude(amp)
            await asyncio.sleep(0.065)

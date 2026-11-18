"""
====================================================================
       CAMERA SERVICE — QUẢN LÝ WEBCAM & CHỤP ẢNH TỰ ĐỘNG
====================================================================
Quản lý thiết bị Camera / Webcam thực tế của hệ thống:
1. Mở webcam qua OpenCV (hỗ trợ V4L2 trên Raspberry Pi 5 và DSHOW trên Windows).
2. Tự động đọc vài frame khởi động (warmup) để cảm biến cân bằng sáng và nét.
3. Chụp ảnh độ phân giải cao khi nhận lệnh TAKE_PHOTO.
4. Tự động lưu ảnh vào thư mục 'screen_shot/' với định dạng:
   screen_shot/photo_YYYYMMDD_HHMMSS.jpg
5. Chuyển đổi sang Base64 Data URL để gửi ngay lên MagicMirror hiển thị xem trước.
6. Ngắt kết nối camera khi ở State 0 (Ngủ) để bảo vệ phần cứng và chống nóng.
====================================================================
"""

import base64
from datetime import datetime
import os
import sys
import threading
import time
from typing import Optional, Dict, Any

# Đảm bảo UTF-8
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Thư viện OpenCV
try:
    import cv2
    HAS_OPENCV = True
except ImportError:
    cv2 = None
    HAS_OPENCV = False

# Thư mục lưu trữ ảnh chụp
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SCREENSHOT_DIR = os.path.join(BASE_DIR, "screen_shot")
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

class CameraService:
    """
    Quản lý Camera / Webcam chụp ảnh độ nét cao.
    """

    def __init__(self, camera_index: Optional[int] = None):
        if camera_index is not None:
            self.camera_index = camera_index
        else:
            env_idx = os.getenv("CAMERA_INDEX")
            try:
                self.camera_index = int(env_idx) if env_idx is not None else 0
            except Exception:
                self.camera_index = 0

        self._lock = threading.Lock()

    def is_available(self) -> bool:
        """Kiểm tra xem webcam có thể mở và đọc được hay không"""
        if not HAS_OPENCV:
            return False
        with self._lock:
            try:
                if os.name != "nt":
                    cap = cv2.VideoCapture(self.camera_index, cv2.CAP_V4L2)
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
                else:
                    cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
                if not cap.isOpened():
                    cap = cv2.VideoCapture(self.camera_index)
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
                if cap.isOpened():
                    ret, _ = cap.read()
                    cap.release()
                    return bool(ret)
                return False
            except Exception:
                return False

    def is_ready(self) -> bool:
        """Kiểm tra trạng thái sẵn sàng của Camera (bí danh cho is_available)"""
        return self.is_available()

    def release(self):
        """Giải phóng camera nếu có tài nguyên giữ (CameraService tự mở/đóng theo từng tác vụ)"""
        pass


    def capture_photo(
        self,
        prefix: str = "photo",
        warmup_frames: int = 5
    ) -> Dict[str, Any]:
        """
        Mở camera, chụp 1 bức ảnh chất lượng cao và đóng camera ngay sau đó.
        
        Returns:
            {
                "success": bool,
                "filename": str,
                "filepath": str,
                "data_url": str (Base64 JPEG),
                "error": str (nếu có lỗi)
            }
        """
        if not HAS_OPENCV:
            return {
                "success": False,
                "error": "Chưa cài đặt OpenCV (opencv-python).",
                "data_url": None,
                "filepath": None
            }

        with self._lock:
            # Trên Linux Pi 5 ưu tiên backend V4L2 với MJPG nén, trên Windows dùng DSHOW hoặc Default
            if os.name != "nt":
                cap = cv2.VideoCapture(self.camera_index, cv2.CAP_V4L2)
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
                cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
            else:
                cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)

            if not cap.isOpened():
                # Fallback sang mở mặc định
                cap = cv2.VideoCapture(self.camera_index)
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
                cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))

            if not cap.isOpened():
                return {
                    "success": False,
                    "error": f"Không thể mở webcam index {self.camera_index}",
                    "data_url": None,
                    "filepath": None
                }

            try:
                # Đọc vài frame khởi động để cảm biến cân bằng sáng
                for _ in range(warmup_frames):
                    cap.read()

                ret, frame = cap.read()
                if not ret or frame is None:
                    return {
                        "success": False,
                        "error": "Không đọc được khung hình từ webcam",
                        "data_url": None,
                        "filepath": None
                    }

                # Lưu file ảnh JPG
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"{prefix}_{timestamp}.jpg"
                filepath = os.path.join(SCREENSHOT_DIR, filename)

                cv2.imwrite(filepath, frame, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
                print(f"[📷 Camera] Đã chụp và lưu ảnh vào: screen_shot/{filename}")

                # Chuyển đổi khung hình sang Base64 Data URL
                success, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 88])
                if success:
                    b64_str = base64.b64encode(buffer).decode("utf-8")
                    data_url = f"data:image/jpeg;base64,{b64_str}"
                else:
                    data_url = None

                return {
                    "success": True,
                    "filename": filename,
                    "filepath": filepath,
                    "data_url": data_url
                }

            except Exception as e:
                return {
                    "success": False,
                    "error": str(e),
                    "data_url": None,
                    "filepath": None
                }
            finally:
                cap.release()

# Bí danh tương thích ngược
RealCamera = CameraService


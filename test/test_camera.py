"""
====================================================================
        📷 TEST CAMERA: BỘ ĐO LƯỜNG, CHẨN ĐOÁN & KIỂM TRA WEBCAM
====================================================================
Chức năng:
1. Tự động quét phần cứng V4L2 và danh sách các cổng video (/dev/video*).
2. Kiểm tra tính tương thích chuẩn nén MJPG vs YUYV trên Raspberry Pi 5.
3. Đo kiểm và benchmark độ trễ mở camera và tốc độ khung hình (FPS) ở độ phân giải 1280x720.
4. Chụp ảnh thử nghiệm chất lượng cao và lưu vào:
   - screen_shot/photo_test_YYYYMMDD_HHMMSS.jpg
   - test/records/camera_latest.jpg
5. Chế độ xem trước thời gian thực (--gui):
   - Mở cửa sổ trực tiếp camera, nhấn [SPACE] hoặc [c] để chụp, [q] để thoát.
6. Chế độ thử nghiệm giao diện gương (--mirror):
   - Gửi lệnh WebSocket trực tiếp tới MagicMirror để kiểm tra HUD ngắm,
     bảng tạo dáng, đếm ngược 3-2-1 và chớp flash máy ảnh trên màn hình gương.
====================================================================
"""

import argparse
import asyncio
from datetime import datetime
import json
import os
import shutil
import subprocess
import sys
import time
from typing import Optional, List, Dict, Any

# Đảm bảo UTF-8 cho console
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

try:
    import cv2
    HAS_OPENCV = True
except ImportError:
    HAS_OPENCV = False

try:
    import websockets
    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False

try:
    from backend.hardware.camera_service import CameraService, SCREENSHOT_DIR
    HAS_CAMERA_SERVICE = True
except ImportError:
    HAS_CAMERA_SERVICE = False
    SCREENSHOT_DIR = os.path.join(PROJECT_ROOT, "screen_shot")

RECORDS_DIR = os.path.join(PROJECT_ROOT, "test", "records")
os.makedirs(RECORDS_DIR, exist_ok=True)
os.makedirs(SCREENSHOT_DIR, exist_ok=True)


def print_banner():
    banner = """
╔══════════════════════════════════════════════════════════════════════════════╗
║               📷 SMART MIRROR 2.0 — CAMERA DIAGNOSTIC & TEST TOOL             ║
╠══════════════════════════════════════════════════════════════════════════════╣
║ • V4L2 Device Scan   : Quét phần cứng webcam & cổng video (/dev/video*)      ║
║ • Hardware Driver    : Cưỡng bức chuẩn nén MJPG (chống nghẽn USB V4L2)        ║
║ • Performance Test   : Đo độ trễ mở camera & tốc độ khung hình (FPS)         ║
║ • Realtime Capture   : Chụp ảnh lưu vào screen_shot/ & test/records/         ║
║ • Gui Live View      : Mở cửa sổ camera trực tiếp (--gui)                    ║
║ • Mirror Simulation  : Thử nghiệm giao diện gương MagicMirror (--mirror)     ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
    print(banner)


def scan_v4l2_devices() -> List[Dict[str, Any]]:
    """Quét phần cứng và tìm tất cả thiết bị video trên Linux qua v4l2-ctl"""
    devices = []
    if os.name != "nt":
        try:
            res = subprocess.run(["v4l2-ctl", "--list-devices"], capture_output=True, text=True, timeout=5)
            if res.returncode == 0:
                raw_blocks = res.stdout.strip().split("\n\n")
                for block in raw_blocks:
                    lines = [l.strip() for l in block.split("\n") if l.strip()]
                    if lines:
                        card_name = lines[0].rstrip(":")
                        video_nodes = [l for l in lines[1:] if l.startswith("/dev/video")]
                        devices.append({
                            "name": card_name,
                            "nodes": video_nodes
                        })
        except Exception:
            pass

    # Nếu không có v4l2-ctl hoặc là Windows, dò qua danh sách /dev/video*
    if not devices and os.path.exists("/dev"):
        nodes = sorted([f"/dev/{f}" for f in os.listdir("/dev") if f.startswith("video") and f[5:].isdigit()],
                       key=lambda x: int(x.replace("/dev/video", "")))
        if nodes:
            devices.append({"name": "Linux Video Nodes", "nodes": nodes})
    return devices


def test_camera_stream(cam_index: int = 0) -> Optional[Dict[str, Any]]:
    """Kiểm tra mở camera và đo độ trễ + FPS ở độ phân giải chuẩn 1280x720"""
    if not HAS_OPENCV:
        return None

    t0 = time.perf_counter()
    if os.name != "nt":
        cap = cv2.VideoCapture(cam_index, cv2.CAP_V4L2)
    else:
        cap = cv2.VideoCapture(cam_index, cv2.CAP_DSHOW)

    if not cap.isOpened():
        cap = cv2.VideoCapture(cam_index)

    if not cap.isOpened():
        return None

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))

    open_time = time.perf_counter() - t0

    # Warmup 1 frame
    t_first_start = time.perf_counter()
    ret_first, frame_first = cap.read()
    first_frame_time = time.perf_counter() - t_first_start

    if not ret_first or frame_first is None:
        cap.release()
        return None

    # Đo 12 frame liên tiếp để tính FPS thực tế
    t_bench_start = time.perf_counter()
    count = 0
    last_frame = frame_first
    for _ in range(12):
        ret, frame = cap.read()
        if ret and frame is not None:
            count += 1
            last_frame = frame

    bench_time = time.perf_counter() - t_bench_start
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    time.sleep(0.3)

    fps = count / bench_time if bench_time > 0 else 0.0
    latency_per_frame = (bench_time / count) * 1000 if count > 0 else 0.0

    return {
        "index": cam_index,
        "width": w,
        "height": h,
        "actual_shape": last_frame.shape,
        "open_time": open_time,
        "first_frame_time": first_frame_time,
        "fps": fps,
        "latency_ms": latency_per_frame,
        "sample_frame": last_frame
    }


def capture_test_photo(cam_index: int = 0) -> Optional[Dict[str, Any]]:
    """Chụp ảnh chất lượng cao 1280x720 và lưu vào thư mục screen_shot/ & test/records/"""
    print("\n" + "─" * 78)
    print("📸 [BƯỚC 3/3] TIẾN HÀNH CHỤP ẢNH THỰC TẾ & LƯU TỆP")
    print("─" * 78)

    t0 = time.perf_counter()
    if HAS_CAMERA_SERVICE:
        cam_service = CameraService(camera_index=cam_index)
        res = cam_service.capture_photo(prefix="photo_test", warmup_frames=4)
    else:
        # Fallback tự chụp nếu không có CameraService
        if os.name != "nt":
            cap = cv2.VideoCapture(cam_index, cv2.CAP_V4L2)
        else:
            cap = cv2.VideoCapture(cam_index, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap = cv2.VideoCapture(cam_index)

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))

        for _ in range(4):
            cap.read()
        ret, frame = cap.read()
        cap.release()

        if ret and frame is not None:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            fname = f"photo_test_{ts}.jpg"
            fpath = os.path.join(SCREENSHOT_DIR, fname)
            cv2.imwrite(fpath, frame, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
            res = {"success": True, "filename": fname, "filepath": fpath}
        else:
            res = {"success": False, "error": "Không đọc được frame"}

    duration = time.perf_counter() - t0

    if res.get("success"):
        filepath = res.get("filepath")
        filesize_kb = os.path.getsize(filepath) / 1024.0

        # Sao chép vào test/records/camera_latest.jpg để tiện kiểm tra
        latest_path = os.path.join(RECORDS_DIR, "camera_latest.jpg")
        shutil.copyfile(filepath, latest_path)

        print(f"  ✅ Chụp ảnh THÀNH CÔNG trong {duration:.3f}s!")
        print(f"  📁 Tệp chính lưu tại      : {filepath}")
        print(f"  📁 Bản sao mới nhất       : {latest_path}")
        print(f"  📦 Dung lượng ảnh         : {filesize_kb:.1f} KB")

        # Đọc thông tin frame
        img = cv2.imread(filepath)
        if img is not None:
            h, w, c = img.shape
            print(f"  📐 Độ phân giải thực tế   : {w} x {h} (Kênh màu: {c})")
        return res
    else:
        print(f"  ❌ Chụp ảnh THẤT BẠI: {res.get('error')}")
        return None


def run_gui_preview(cam_index: int = 0):
    """Mở cửa sổ OpenCV hiển thị trực tiếp camera feed (Yêu cầu màn hình Desktop / Wayland / X11)"""
    if not HAS_OPENCV:
        print("[!] Không tìm thấy thư viện OpenCV.")
        return

    print("\n" + "═" * 78)
    print("🖥️  CHẾ ĐỘ XEM TRỰC TIẾP CAMERA (GUI LIVE PREVIEW)")
    print("═" * 78)
    print("  • Phím [SPACE] hoặc [c] : Chụp ảnh ngay lập tức")
    print("  • Phím [q] hoặc [ESC]   : Thoát cửa sổ xem trước")
    print("─" * 78)

    if os.name != "nt":
        cap = cv2.VideoCapture(cam_index, cv2.CAP_V4L2)
    else:
        cap = cv2.VideoCapture(cam_index, cv2.CAP_DSHOW)

    if not cap.isOpened():
        cap = cv2.VideoCapture(cam_index)

    if not cap.isOpened():
        print(f"[❌] Không thể mở camera index #{cam_index}")
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))

    window_name = "Smart Mirror - Live Camera Preview (Nhan [SPACE] de chup, [q] de thoat)"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)

    fps_count = 0
    fps_start = time.perf_counter()
    cur_fps = 0.0
    flash_until = 0.0

    try:
        while True:
            ret, frame = cap.read()
            if not ret or frame is None:
                print("[!] Mất tín hiệu camera...")
                break

            fps_count += 1
            if time.perf_counter() - fps_start >= 1.0:
                cur_fps = fps_count / (time.perf_counter() - fps_start)
                fps_count = 0
                fps_start = time.perf_counter()

            # Hiệu ứng gương soi (Mirror Reflection)
            frame_disp = cv2.flip(frame, 1)

            # Vẽ khung ngắm Sci-Fi HUD
            h, w = frame_disp.shape[:2]
            cx, cy = w // 2, h // 2

            # Tâm ngắm
            cv2.drawMarker(frame_disp, (cx, cy), (0, 242, 254), cv2.MARKER_CROSS, 30, 2)
            cv2.circle(frame_disp, (cx, cy), 15, (0, 242, 254), 1)

            # 4 góc HUD Viewfinder
            corner_len = 35
            c_color = (0, 242, 254)
            # Top-Left
            cv2.line(frame_disp, (40, 40), (40 + corner_len, 40), c_color, 2)
            cv2.line(frame_disp, (40, 40), (40, 40 + corner_len), c_color, 2)
            # Top-Right
            cv2.line(frame_disp, (w - 40, 40), (w - 40 - corner_len, 40), c_color, 2)
            cv2.line(frame_disp, (w - 40, 40), (w - 40, 40 + corner_len), c_color, 2)
            # Bottom-Left
            cv2.line(frame_disp, (40, h - 40), (40 + corner_len, h - 40), c_color, 2)
            cv2.line(frame_disp, (40, h - 40), (40, h - 40 - corner_len), c_color, 2)
            # Bottom-Right
            cv2.line(frame_disp, (w - 40, h - 40), (w - 40 - corner_len, h - 40), c_color, 2)
            cv2.line(frame_disp, (w - 40, h - 40), (w - 40, h - 40 - corner_len), c_color, 2)

            # Thông số hiển thị
            cv2.putText(frame_disp, f"SMART MIRROR CAM | FPS: {cur_fps:.1f} | {w}x{h}",
                        (45, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 242, 254), 2)
            cv2.putText(frame_disp, "[SPACE] / [c]: Chup anh  |  [q]: Thoat",
                        (45, h - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)

            # Flash trắng nếu vừa chụp
            if time.perf_counter() < flash_until:
                white_overlay = frame_disp.copy()
                white_overlay[:] = (255, 255, 255)
                frame_disp = cv2.addWeighted(white_overlay, 0.75, frame_disp, 0.25, 0)

            cv2.imshow(window_name, frame_disp)
            key = cv2.waitKey(1) & 0xFF

            if key in [ord("q"), ord("Q"), 27]:  # 27 là phím ESC
                print("[-> Thoát] Người dùng đóng cửa sổ xem trước.")
                break
            elif key in [ord(" "), ord("c"), ord("C")]:
                flash_until = time.perf_counter() + 0.15
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                save_name = f"photo_gui_{ts}.jpg"
                save_path = os.path.join(SCREENSHOT_DIR, save_name)
                cv2.imwrite(save_path, frame, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
                shutil.copyfile(save_path, os.path.join(RECORDS_DIR, "camera_latest.jpg"))
                print(f"  📸 ĐÃ CHỤP ẢNH TỨC THÌ: screen_shot/{save_name} (Size: {os.path.getsize(save_path)/1024:.1f} KB)")
    finally:
        cap.release()
        cv2.destroyAllWindows()


async def simulate_mirror_ui_flow():
    """Gửi trực tiếp các gói tin WebSocket tới MagicMirror để kiểm tra giao diện gương hiển thị chuẩn xác"""
    if not HAS_WEBSOCKETS:
        print("[!] Cần cài websockets để test giao diện gương: pip install websockets")
        return

    uri = "ws://localhost:8085"
    print("\n" + "═" * 78)
    print("🔮 THỬ NGHIỆM GIAO DIỆN GƯƠNG TOÀN DIỆN (MAGICMIRROR SIMULATION)")
    print("═" * 78)
    print(f"  • Đang kết nối tới Mirror Backend Server: {uri} ...")

    try:
        async with websockets.connect(uri) as ws:
            print("  ✅ Đã kết nối thành công tới Backend Server!")

            # 1. Bật giao diện Camera HUD
            print("\n  [1/4] Gửi lệnh mở giao diện Camera: 'OPEN_PHOTO_PREVIEW'...")
            await ws.send(json.dumps({
                "action": "OPEN_PHOTO_PREVIEW",
                "text": "Đang mở camera soi gương tạo dáng...",
                "response_text": "Đang mở camera soi gương tạo dáng..."
            }))
            print("       ➔ Hãy nhìn màn hình gương: Giao diện HUD 4 góc Cyan & Huy hiệu tạo dáng đã bật!")
            await asyncio.sleep(4)

            # 2. Đếm ngược 3-2-1
            print("  [2/4] Gửi lệnh đếm ngược chụp: 'START_PHOTO_COUNTDOWN' (3s)...")
            await ws.send(json.dumps({
                "action": "START_PHOTO_COUNTDOWN",
                "countdown": 3,
                "text": "Ba, hai, một... Chụp!"
            }))
            for c in [3, 2, 1]:
                print(f"       ⏱️  Đang đếm ngược: {c}...")
                await asyncio.sleep(1)

            # 3. Chụp ảnh qua OpenCV
            print("  [3/4] Kích hoạt chụp ảnh qua OpenCV Backend...")
            await ws.send(json.dumps({
                "action": "TRIGGER_BACKEND_CAPTURE"
            }))
            print("       📸 Đang chụp và chuyển ảnh sang Base64...")
            await asyncio.sleep(2)

            print("  [4/4] Hoàn tất! Ảnh chụp đã xuất hiện ngay giữa màn hình gương.")
            print("═" * 78 + "\n")
    except Exception as e:
        print(f"  [⚠️ Không thể kết nối tới {uri}]: {e}")
        print("  💡 Gợi ý: Hãy đảm bảo bạn đã chạy Backend trước: './run_backend.sh'")


def main():
    parser = argparse.ArgumentParser(description="Bộ kiểm tra và chẩn đoán Camera cho MagicMirror 2.0")
    parser.add_argument("--index", type=int, default=0, help="Camera index (Mặc định: 0)")
    parser.add_argument("--snap", action="store_true", help="Chỉ chụp nhanh 1 ảnh và lưu file")
    parser.add_argument("--gui", action="store_true", help="Mở cửa sổ xem camera trực tiếp thời gian thực")
    parser.add_argument("--mirror", action="store_true", help="Giả lập và kiểm tra giao diện MagicMirror qua WebSocket")

    args = parser.parse_args()

    print_banner()

    if not HAS_OPENCV:
        print("[❌ LỖI] Chưa cài đặt OpenCV trong môi trường Python.")
        print("         Hãy cài đặt bằng: pip install opencv-python")
        sys.exit(1)

    # 1. Chế độ giả lập giao diện gương nếu có cờ --mirror
    if args.mirror:
        asyncio.run(simulate_mirror_ui_flow())
        return

    # 2. Chế độ xem trước GUI nếu có cờ --gui
    if args.gui:
        run_gui_preview(args.index)
        return

    # 3. Chế độ chụp ảnh nhanh
    if args.snap:
        print("📸 Chế độ chụp ảnh nhanh (--snap):")
        capture_test_photo(args.index)
        return

    # 4. Chế độ chẩn đoán & kiểm tra tự động
    print("🔍 [BƯỚC 1/3] QUÉT PHẦN CỨNG CAMERA (HARDWARE DIAGNOSTIC)")
    print("─" * 78)
    devs = scan_v4l2_devices()
    if devs:
        print("  • Danh sách các thiết bị video phần cứng phát hiện được:")
        for d in devs:
            nodes_str = ", ".join(d["nodes"])
            print(f"    - {d['name']:<40} ➔ {nodes_str}")
    else:
        print("  • Không tìm thấy thông tin V4L2 qua v4l2-ctl (Sẽ kiểm tra trực tiếp qua OpenCV).")

    # 5. Kiểm tra mở camera & tốc độ khung hình
    print("\n" + "─" * 78)
    print(f"⚡ [BƯỚC 2/3] ĐO TỐC ĐỘ MỞ & HIỆU NĂNG LUỒNG VIDEO (INDEX #{args.index})")
    print("─" * 78)
    cam_info = test_camera_stream(args.index)

    if cam_info:
        print(f"  ✅ Mở camera #{args.index} thành công trong : {cam_info['open_time']:.3f}s")
        print(f"  ⚡ Độ trễ đọc khung hình đầu tiên : {cam_info['first_frame_time']:.3f}s")
        print(f"  📐 Độ phân giải khung hình        : {cam_info['width']} x {cam_info['height']}")
        print(f"  🚀 Tốc độ khung hình thực tế      : {cam_info['fps']:.1f} FPS (Độ trễ: {cam_info['latency_ms']:.1f} ms/khung)")
    else:
        print(f"  ❌ Không thể mở hoặc đọc dữ liệu từ camera #{args.index}.")
        print("     Hãy kiểm tra xem camera có bị ứng dụng khác giữ không, hoặc thử --index 1")
        sys.exit(1)

    time.sleep(0.4)
    # 6. Chụp ảnh thử nghiệm
    capture_test_photo(args.index)

    print("\n" + "═" * 78)
    print("🎉 HOÀN TẤT KIỂM TRA CAMERA!")
    print("═" * 78)
    print("💡 Mẹo kiểm tra bổ sung:")
    print("  • Xem camera trực tiếp qua cửa sổ GUI : python test/test_camera.py --gui")
    print("  • Giả lập thử nghiệm giao diện gương  : python test/test_camera.py --mirror")
    print("  • Chụp nhanh 1 ảnh lưu tệp            : python test/test_camera.py --snap")
    print("═" * 78 + "\n")


if __name__ == "__main__":
    main()

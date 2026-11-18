#!/bin/bash
# ====================================================================
#     🔮 SMART MIRROR 2.0 - LINUX / RASPBERRY PI MASTER RUNNER
# ====================================================================
# Tự động khởi chạy cả Python AI Backend và Cửa sổ Giao diện Gương Chính
# ====================================================================

set -e

SOURCE="${BASH_SOURCE[0]}"
while [ -h "$SOURCE" ]; do
    DIR="$( cd -P "$( dirname "$SOURCE" )" >/dev/null 2>&1 && pwd )"
    SOURCE="$(readlink "$SOURCE")"
    [[ $SOURCE != /* ]] && SOURCE="$DIR/$SOURCE"
done
PROJECT_DIR="$( cd -P "$( dirname "$SOURCE" )" >/dev/null 2>&1 && pwd )"

cd "$PROJECT_DIR"

echo "===================================================================="
echo "    🔮 SMART MIRROR 2.0 - ALL-IN-ONE (LINUX / RASPBERRY PI)"
echo "===================================================================="

# 1. Giải phóng các port nếu có phiên cũ đang chiếm
fuser -k 8080/tcp 8085/tcp 8086/tcp >/dev/null 2>&1 || true

# 2. Biên dịch Web Hub nếu chưa có thư mục web/dist
if [ ! -f "web/dist/index.html" ]; then
    echo "[1/3] Đang biên dịch Companion Web Hub (Vite + React)..."
    npm --prefix web run build
    echo "[✓] Đã tạo thành công thư mục web/dist!"
fi

# 3. Kích hoạt môi trường ảo Python
if [ -f ".MMenv/bin/activate" ]; then
    source .MMenv/bin/activate
elif [ -f "$PROJECT_DIR/.MMenv/bin/activate" ]; then
    source "$PROJECT_DIR/.MMenv/bin/activate"
else
    echo "[!] Không tìm thấy .MMenv, sử dụng python3 mặc định..."
fi

export PYTHONUNBUFFERED=1

# 4. Khởi chạy Python AI Backend chạy ngầm
echo "[2/3] Đang khởi động Python AI Backend (Voice, Camera, Gemini, WebSocket)..."
python3 backend/app_main.py &
BACKEND_PID=$!

# Bắt sự kiện tắt script để tự dọn dẹp process con
trap "echo 'Đang tắt toàn bộ hệ thống...'; kill $BACKEND_PID 2>/dev/null || true; exit 0" SIGINT SIGTERM EXIT

sleep 2

# 5. Khởi chạy Giao diện Gương Chính (Desktop GUI Window trên màn hình Pi)
echo "[3/3] Đang bật Cửa sổ Giao diện Gương Chính lên màn hình..."
echo ""
echo "===================================================================="
echo " ✨ HỆ THỐNG ĐÃ SẴN SÀNG!"
echo " 🖥️  Cửa sổ Gương Thông Minh đang hiển thị toàn màn hình."
echo " 🌐  Web Hub quản lý (IoT, Lịch, Ảnh): http://$(hostname -I 2>/dev/null | awk '{print $1}'):8080/web"
echo "===================================================================="
echo ""

# Tự động gán Display nếu chạy qua SSH hoặc autostart
export DISPLAY="${DISPLAY:=:0}"

# Nhận diện tự động chuẩn hiển thị: Wayland (Raspberry Pi 5) hoặc X11 (Raspberry Pi 4 / PC Linux)
if [ -n "$WAYLAND_DISPLAY" ] || [ -e "$XDG_RUNTIME_DIR/wayland-0" ] || [ -e "$XDG_RUNTIME_DIR/wayland-1" ]; then
    export WAYLAND_DISPLAY="${WAYLAND_DISPLAY:=wayland-1}"
    npm run start:wayland
elif [ -n "$DISPLAY" ]; then
    npm run start:x11
else
    # Fallback nếu không có màn hình cắm vào
    echo "[!] Không phát hiện màn hình vật lý, chạy ở chế độ máy chủ ngầm (Headless)..."
    node serveronly
fi

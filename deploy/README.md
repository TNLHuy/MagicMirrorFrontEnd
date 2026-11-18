# 🚀 THƯ MỤC CẤU HÌNH & TỰ ĐỘNG HÓA RASPBERRY PI 5

Thư mục này chứa các tệp kịch bản tự động hóa và dịch vụ hệ thống cho Raspberry Pi 5 (8GB):

## 1. `systemd/`
- `smart-mirror-backend.service`: Tự động khởi động Backend Python AI & Voice Engine khi cắm nguồn.
- `smart-mirror-kiosk.service`: Tự động mở giao diện MagicMirror² dưới chế độ toàn màn hình (Electron Kiosk Mode trên Wayland).

## 2. `scripts/`
- `setup_pi5_env.sh`: Kịch bản cài đặt trọn gói môi trường (Python 3, Node.js, PipeWire, ONNX Runtime ARM64, OpenCV V4L2).
- `setup_audio_bluetooth.sh`: Cấu hình tự động kết nối Loa Bluetooth và định tuyến âm thanh PipeWire.
- `rotate_screen_portrait.sh`: Lệnh cấu hình xoay màn hình 15.6" sang chế độ dọc (1080x1920) trên Wayland/X11.


#!/bin/bash
# ====================================================================
#         SMART MIRROR 2.0 — BACKEND APPLIANCE RUNNER
# ====================================================================
# Tự động tìm thư mục gốc dự án MagicMirror (kể cả khi chạy từ thư mục con),
# kích hoạt môi trường ảo Python và khởi chạy Master Backend.
# ====================================================================

set -e

# Tìm đường dẫn thực tế của thư mục gốc dự án (hỗ trợ cả symlink)
SOURCE="${BASH_SOURCE[0]}"
while [ -h "$SOURCE" ]; do
    DIR="$( cd -P "$( dirname "$SOURCE" )" >/dev/null 2>&1 && pwd )"
    SOURCE="$(readlink "$SOURCE")"
    [[ $SOURCE != /* ]] && SOURCE="$DIR/$SOURCE"
done
PROJECT_DIR="$( cd -P "$( dirname "$SOURCE" )" >/dev/null 2>&1 && pwd )"

cd "$PROJECT_DIR"

if [ -f ".MMenv/bin/activate" ]; then
    source .MMenv/bin/activate
elif [ -f "$PROJECT_DIR/.MMenv/bin/activate" ]; then
    source "$PROJECT_DIR/.MMenv/bin/activate"
else
    echo "[!] Không tìm thấy môi trường ảo .MMenv, sử dụng python3 mặc định của hệ thống..."
fi

export PYTHONUNBUFFERED=1

# Tự động giải phóng cổng 8085 nếu có phiên chạy cũ còn sót lại
fuser -k 8085/tcp >/dev/null 2>&1 || true

exec python3 backend/app_main.py "$@"

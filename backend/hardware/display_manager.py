"""
====================================================================
       DISPLAY MANAGER — ĐIỀU KHIỂN NGUỒN MÀN HÌNH 15.6 INCH
====================================================================
Quản lý bật / tắt đèn nền màn hình thực tế (Hardware Screen Power):
- State 0 (Ngủ / Standby):
    * Gửi lệnh ngắt tín hiệu HDMI (DPMS):
      - Trên Wayland Pi 5: 'wlopm --off *'
      - Trên X11 Pi: 'xset dpms force off'
    * Màn hình 15.6" tắt đèn nền đen tuyền hoàn toàn, hóa thành gương soi phẳng.
- State 1 (Thức / Active):
    * Gửi lệnh bật nguồn màn hình:
      - Trên Wayland Pi 5: 'wlopm --on *'
      - Trên X11 Pi: 'xset dpms force on'
    * Màn hình lập tức sáng lại ngay khi nghe "Hey mirror".
====================================================================
"""

import os
import subprocess
import sys
import time

class DisplayManager:
    """
    Quản lý chế độ tiết kiệm điện và bật/tắt đèn nền màn hình.
    """

    def __init__(self):
        self.is_screen_on = True

    def turn_off(self) -> bool:
        """Tắt màn hình (Chuyển sang State 0)"""
        self.is_screen_on = False
        print("[🖥️ Display] Đang tắt đèn nền màn hình (State 0 - Sleep)...")

        if os.name != "nt":
            # 1. Thử lệnh Wayland (Raspberry Pi OS Bookworm)
            try:
                res = subprocess.run(["wlopm", "--off", "*"], capture_output=True, timeout=2)
                if res.returncode == 0:
                    return True
            except Exception:
                pass

            # 2. Thử lệnh X11 DPMS
            try:
                res = subprocess.run(["xset", "dpms", "force", "off"], capture_output=True, timeout=2)
                if res.returncode == 0:
                    return True
            except Exception:
                pass

            # 3. Thử lệnh vcgencmd (Raspberry Pi legacy)
            try:
                res = subprocess.run(["vcgencmd", "display_power", "0"], capture_output=True, timeout=2)
                if res.returncode == 0:
                    return True
            except Exception:
                pass
        else:
            # Trên Windows khi dev/test
            print("[🖥️ Display (Windows)] Mô phỏng tắt màn hình State 0 thành công.")
            return True

        return False

    def turn_on(self) -> bool:
        """Bật lại màn hình (Chuyển sang State 1)"""
        self.is_screen_on = True
        print("[🖥️ Display] Đang bật lại màn hình (State 1 - Active)...")

        if os.name != "nt":
            # 1. Thử lệnh Wayland
            try:
                res = subprocess.run(["wlopm", "--on", "*"], capture_output=True, timeout=2)
                if res.returncode == 0:
                    return True
            except Exception:
                pass

            # 2. Thử lệnh X11
            try:
                res = subprocess.run(["xset", "dpms", "force", "on"], capture_output=True, timeout=2)
                if res.returncode == 0:
                    return True
            except Exception:
                pass

            # 3. Thử lệnh vcgencmd
            try:
                res = subprocess.run(["vcgencmd", "display_power", "1"], capture_output=True, timeout=2)
                if res.returncode == 0:
                    return True
            except Exception:
                pass
        else:
            # Trên Windows
            print("[🖥️ Display (Windows)] Mô phỏng bật màn hình State 1 thành công.")
            return True

        return False

# Singleton
_display_manager_instance = None

def get_display_manager() -> DisplayManager:
    global _display_manager_instance
    if _display_manager_instance is None:
        _display_manager_instance = DisplayManager()
    return _display_manager_instance


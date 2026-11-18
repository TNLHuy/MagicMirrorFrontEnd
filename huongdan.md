# 🔮 HƯỚNG DẪN CẤU HÌNH & VẬN HÀNH TRỢ LÝ AI GƯƠNG THÔNG MINH (MAGICMIRROR2)

Dự án đã được tích hợp toàn diện: **Phát Nhạc Thật (Real Audio Engine + Thư viện `music/`)**, **Google Gemini AI Engine Siêu Tốc (gemini-3.5-flash-lite)**, **Khung Bong Bóng Tròn Hoàn Hảo (Circular Orb Bubble)**, **Thanh Bottom Bar Tinh Gọn (Chỉ hiện 'Sẵn sàng')**, **Nhận diện giọng nói tiếng Việt tự động rảnh tay (Hands-Free Speech-to-Text)**, **Camera Webcam thật lưu vào `screen_shot/`**, và **Micro thật điều khiển sóng Siri Wave thời gian thực**.

---

## 🗺️ 1. Bố Cục Không Gian Mặt Gương (Layout Mapping)

Giao diện được phân bổ chuẩn xác theo sơ đồ **NLU Router 10 Action**:

```text
+-----------------------------------------------------------------------------------+
|  [TOP_LEFT]                                                     [TOP_RIGHT]       |
|  - Đồng hồ số & Thứ Ngày                                        - Thời tiết       |
|    (GET_TIME, GET_DATE)                                           (SHOW_WEATHER)  |
+-----------------------------------------------------------------------------------+
|                                  [MIDDLE_CENTER]                                  |
|                             (KHU VỰC TƯƠNG TÁC ĐỘNG)                              |
|                                                                                   |
|  ✦ NONE       : KHUNG BONG BÓNG TRÒN (Quả cầu AI phản hồi câu hỏi / trò chuyện)   |
|  ✦ SEARCH(web): Popup hình ảnh tìm kiếm từ Internet                               |
|  ✦ SEARCH(cam): Quét laser thị giác camera + Nhãn nhận diện đồ vật (Vision AI)   |
|  ✦ TAKE_PHOTO : Vòng tròn đếm ngược 3-2-1 + Chớp Flash + Xem trước ảnh vừa chụp  |
|                                                                                   |
+-----------------------------------------------------------------------------------+
|  [BOTTOM_LEFT]                                                  [BOTTOM_RIGHT]    |
|  - Lịch trình cá nhân                                           - Mini Music      |
|    (GET_CALENDAR)                                                 (PLAY_MEDIA)    |
|                                                                 - SmartHome       |
|                                                                   (SMART_HOME)    |
+-----------------------------------------------------------------------------------+
|                                   [BOTTOM_BAR]                                    |
|   ✦ Trạng thái: [Sẵn sàng / Đang nghe] | Sóng Siri rung giọng nói | Đo âm lượng   |
+-----------------------------------------------------------------------------------+
```

---

## ⚙️ 2. Hệ Thống 2 State Hoạt Động

| State | Tên gọi | Mô tả hành vi |
| :---: | :--- | :--- |
| **State 0** | **Sleep (Ngủ / Standby)** | Màn hình tắt đen hoàn toàn, ẩn toàn bộ widget để tiết kiệm điện, tự động tạm dừng phát nhạc. |
| **State 1** | **Active (Hoạt động)** | Bật các widget tĩnh ở 4 góc (`clock`, `weather`, `calendar`, mini music & smarthome) và kích hoạt Trợ lý AI ở thanh đáy. |

---

## 🚀 3. Những Tính Năng Đã Hoàn Thiện & Nâng Cấp

### 1. 🎵 Phát Nhạc Thật (Real Audio Music Player)
- **Đã phát được âm thanh thật ra loa**: Tích hợp HTML5 Audio Engine vào MagicMirror, không chỉ hiển thị giao diện mà còn phát nhạc thực tế ra loa.
- **Thư mục nhạc riêng `modules/MMM-StateControl/music/`**:
  - Đã có sẵn bản nhạc thư giãn mẫu `sample_chill.mp3` và bài hát của bạn `noi_nay_co_anh.mp3`.
  - Bạn có thể **thả bất kỳ file nhạc `.mp3` nào bạn thích** vào thư mục `modules/MMM-StateControl/music/`.
  - Khi nói *"Bật bài Nơi này có anh"*, hệ thống sẽ tự động quét thư mục và phát đúng bài đó!
- **Hỗ trợ Radio Lo-Fi Stream 24/7**: Khi không tìm thấy file nhạc offline tương ứng, hệ thống tự động kết nối luồng âm thanh thư giãn trực tuyến chất lượng cao.
- **Điều khiển bật / tắt linh hoạt**:
  - Bật nhạc: *"Bật nhạc", "Mở bài hát..."* $\rightarrow$ Đĩa nhạc xoay, sóng nhảy múa và nhạc vang lên.
  - Tắt nhạc: *"Tắt nhạc", "Dừng nhạc", "Tạm dừng"* $\rightarrow$ Nhạc dừng phát ngay lập tức.
  - Tự động dừng nhạc khi gương chuyển sang `State 0` (Đi ngủ).

### 2. 🟢 Thanh Bottom Bar Tinh Gọn (Xóa chữ 'Hey Mirror')
- **Đã xóa bỏ hoàn toàn chữ `(Nói 'Hey Mirror')`**:
  - Ở trạng thái bình thường, thanh đáy chỉ hiển thị: **`✦ Sẵn sàng`** gọn gàng, tinh tế và chuyên nghiệp.
  - Khi bạn nói, thanh sẽ tự động đổi sang `Đang lắng nghe...` $\rightarrow$ `Đang nhận dạng...` $\rightarrow$ `Đang xử lý...`.

### 3. 🫧 Khung Bong Bóng Tròn Hoàn Hảo (Circular Orb Bubble)
- **Thiết kế quả cầu hình tròn**: Chuyển đổi khung thành hình tròn hoàn hảo (`border-radius: 50%`, `aspect-ratio: 1 / 1`).
- **Đã loại bỏ 3 hình thoi / chấm tròn chéo**: Đã bỏ hoàn toàn cụm đuôi suy nghĩ cũ, chỉ giữ lại quả cầu pha lê lơ lửng phát sáng viền neon kép.
- **Vệt phản quang cong 3D**: Vòm sáng cong phản chiếu ôm theo đường cong đỉnh quả cầu tạo hiệu ứng chiều sâu lộng lẫy.

### 4. ⚡ AI Phản Hồi Siêu Tốc (Dưới 1-2 Giây)
- **Model `gemini-3.5-flash-lite`**: Tốc độ suy luận chỉ ~0.8s, không bị nghẽn quota 20 req/ngày như bản cũ.
- **Rút ngắn độ trễ Micro VAD**: Nhận diện dứt câu nhanh hơn 400ms và gửi đi xử lý ngay.
- **Gõ chữ tức thì**: Chữ hiển thị mượt mà trên gương trong chớp mắt.

---

## 🗣️ 4. Bảng Tra Cứu Khẩu Lệnh Giọng Nói (10 Action)

Chỉ cần cất tiếng nói trước gương, trợ lý AI sẽ tự động xử lý:

| Khẩu lệnh giọng nói mẫu | Action được kích hoạt | Hành vi thực tế trên gương |
| :--- | :---: | :--- |
| *"Bật bài Nơi này có anh"* / *"Bật nhạc lên"* | `PLAY_MEDIA` | `[BOTTOM_RIGHT]` **Phát nhạc thật ra loa**, đĩa xoay, sóng nhảy |
| *"Tắt nhạc đi"* / *"Dừng nhạc"* | `PLAY_MEDIA` | `[BOTTOM_RIGHT]` **Tạm dừng phát nhạc** ngay lập tức |
| *"Chụp cho tôi một bức ảnh"* | `TAKE_PHOTO` | `[MIDDLE_CENTER]` Đếm ngược 3s + Chụp ảnh webcam + Lưu `screen_shot/` |
| *"Bật đèn phòng khách"* / *"Tắt máy lạnh"* | `SMART_HOME` | `[BOTTOM_RIGHT]` Cập nhật trạng thái thiết bị nhà thông minh |
| *"Bây giờ là mấy giờ rồi?"* | `GET_TIME` | `[MIDDLE_CENTER]` Trả lời giờ trong Quả cầu AI Tròn |
| *"Hôm nay thời tiết thế nào?"* | `SHOW_WEATHER` | `[MIDDLE_CENTER]` Trả lời thời tiết trong Quả cầu AI Tròn |
| *"Hôm nay là ngày mấy?"* | `GET_DATE` | `[MIDDLE_CENTER]` Trả lời ngày tháng trong Quả cầu AI Tròn |
| *"Tôi có lịch trình gì hôm nay không?"* | `GET_CALENDAR` | `[MIDDLE_CENTER]` Đọc lịch trình trong Quả cầu AI Tròn |
| *"Cho tôi xem ảnh tháp Eiffel"* | `SEARCH (web_image)` | `[MIDDLE_CENTER]` Popup hiển thị ảnh tìm kiếm toàn màn hình |
| *"Xem trước camera đây là cái gì"* | `SEARCH (camera)` | `[MIDDLE_CENTER]` Chụp webcam + Quét laser + Tag nhận diện vật thể |
| *"Bạn là ai?"* / *"Kể chuyện vui đi"* | `NONE` | `[MIDDLE_CENTER]` Gemini AI trò chuyện tự do trong Quả cầu AI Tròn |
| *"Tắt màn hình đi ngủ"* | `SYSTEM` (State 0) | Màn hình tắt đen, dừng phát nhạc |
| *"Thức dậy nào"* | `SYSTEM` (State 1) | Bật lại đầy đủ các widget tĩnh |

---

## 💻 5. Hướng Dẫn Vận Hành Hiện Tại (Windows)

### Bước 1: Khởi động Backend Python (AI + Micro + Camera + Nhạc)
Mở cửa sổ Terminal (PowerShell hoặc CMD) và chạy:
```powershell
python cli_controller.py
```

### Bước 2: Khởi động Giao diện MagicMirror
Mở cửa sổ Terminal thứ hai và chạy:
```powershell
npm.cmd run start:windows
```

---

## ⌨️ 6. Bảng Phím Tắt Tiện Ích Trong Terminal `cli_controller.py`

| Phím tắt | Chức năng |
| :---: | :--- |
| **Nói vào mic** | Tự động nhận diện câu nói và thực thi hoàn toàn rảnh tay (Hands-free) |
| **Gõ câu chữ** | Gõ bất kỳ câu tiếng Việt nào rồi nhấn Enter -> Gemini AI phân tích ngay |
| `m` | **Bật phát nhạc** (Phát bài mẫu hoặc bài trong thư mục `music/`) |
| `0` | Chuyển sang State 0 (Ngủ / Màn hình tắt đen / Tạm dừng nhạc) |
| `1` | Chuyển sang State 1 (Thức / Hiện Widget tĩnh 4 góc) |
| `wake` | **Test đánh thức 'Hey Mirror'** (Giả lập khi chưa cắm Micro) |
| `mic` | Bật / Tắt micro và tính năng nhận diện giọng nói |
| `p` | Test nhanh Action `TAKE_PHOTO` (Đếm ngược 3s + chụp webcam) |
| `c` | Test nhanh Action `SEARCH (camera)` (Chụp webcam + Quét thị giác) |
| `s` | Test nhanh Quả cầu AI tròn trả lời |
| `w` | Test nhanh Action `SEARCH (web_image)` |
| `h` | Test nhanh Action `SMART_HOME` |
| `i` | Action `IDLE` (Đóng tất cả popup ở giữa gương) |
| `key <API_KEY>` | Nhập API Key Gemini mới nếu cần đổi khóa |
| `q` | Thoát chương trình |

---

## 📂 7. Thư Mục Nhạc `modules/MMM-StateControl/music/`

- Để thêm các bài hát yêu thích:
  1. Chỉ cần copy file `.mp3` (ví dụ: `noi_nay_co_anh.mp3`, `thien_ly_oi.mp3`, v.v.) vào thư mục:
     ```text
     modules/MMM-StateControl/music/
     ```
  2. Nói với gương: *"Bật bài Nơi này có anh"* hoặc *"Bật nhạc lên"*, hệ thống sẽ tự động tìm và phát file nhạc đó ra loa!

---

## 🍓 8. Hướng Dẫn Chuyển Sang Raspberry Pi 5 (Linux) & USB Camera Có Mic

Khi bạn chuyển toàn bộ dự án từ máy tính Windows sang **Raspberry Pi 5** chạy hệ điều hành **Raspberry Pi OS (64-bit Debian Bookworm)** và sử dụng **USB Camera có tích hợp Microphone**, hãy làm theo hướng dẫn chuẩn từng bước sau:

### 1. Kết Nối Phần Cứng (Hardware Setup)
- **USB Camera + Mic**: Cắm trực tiếp vào **cổng USB 3.0** (cổng màu xanh dương) trên Raspberry Pi 5 để đảm bảo băng thông truyền tải hình ảnh và âm thanh mượt mà nhất.
- **Loa / Âm thanh ra**: Bạn có thể xuất âm thanh qua cổng Micro-HDMI (lên màn hình gương có loa), loa gắn cổng USB Audio, hoặc loa Bluetooth.
- **Nguồn điện khuyên dùng**: Sử dụng nguồn chính hãng **USB-C 27W (5V/5A)** của Raspberry Pi 5 để không bị hiện tượng sụt áp khi vừa chạy AI, camera và xử lý âm thanh.

### 2. Cài Đặt Thư Viện Hệ Thống Trên Linux (APT Dependencies)
Khác với Windows, trên Linux bạn cần cài đặt các driver âm thanh ALSA, PortAudio và các công cụ xử lý camera:
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-pip python3-dev python3-venv portaudio19-dev libasound2-dev libatlas-base-dev v4l-utils alsa-utils ffmpeg
```

Cấp quyền truy cập camera và âm thanh cho người dùng hiện tại:
```bash
sudo usermod -aG audio,video $USER
```
*(Khởi động lại Pi hoặc đăng xuất rồi đăng nhập lại để quyền có hiệu lực)*.

### 3. Kiểm Tra Thiết Bị Nhận Diện Trên Linux
Mở Terminal trên Pi và kiểm tra:
* **Kiểm tra Camera:**
  ```bash
  ls -l /dev/video*
  # Hoặc xem chi tiết:
  v4l2-ctl --list-devices
  ```
  *(Thường USB Camera sẽ xuất hiện là `/dev/video0`)*.

* **Kiểm tra Microphone của USB Camera:**
  ```bash
  arecord -l
  ```
  *(Bạn sẽ thấy danh sách card âm thanh đầu vào, ví dụ: `card 1: Device [USB Camera Audio], device 0`)*.

* **Cân chỉnh âm lượng Micro thu âm:**
  ```bash
  alsamixer
  ```
  - Bấm phím **F6** để chọn đúng thiết bị `USB Camera / Audio Device`.
  - Dùng phím mũi tên chuyển sang mục `Capture`, bấm phím mũi tên Lên để kéo âm lượng thu âm lên **85% - 100%**.
  - Bấm phím **Esc** để thoát.

### 4. Thiết Lập Môi Trường Ảo Python Trên Pi 5
Hệ điều hành Raspberry Pi OS Bookworm yêu cầu sử dụng môi trường ảo (`venv`):
```bash
cd ~/MagicMirror-master
python3 -m venv venv --system-site-packages
source venv/bin/activate
pip install --upgrade pip
pip install google-genai SpeechRecognition sounddevice numpy websockets opencv-python-headless
```

### 5. Những Chỗ Cần Chỉnh Sửa Trong Mã Nguồn

Code của dự án đã được thiết kế sẵn để tương thích hoàn toàn giữa Windows và Linux. Bạn chỉ cần chú ý:

1. **File `.env`**:
   Đảm bảo file `.env` nằm ở thư mục gốc của dự án với nội dung:
   ```env
   GEMINI_API_KEY=YOUR_GEMINI_API_KEY
   ```
2. **Cấu hình Camera Index & Mic Device Index (Nếu Pi có nhiều thiết bị)**:
   Nếu Pi nhận diện USB Camera không phải index 0 (ví dụ `/dev/video2`), hoặc có nhiều micro, bạn không cần sửa code Python mà chỉ việc thêm vào file `.env`:
   ```env
   CAMERA_INDEX=0
   MIC_DEVICE_INDEX=1
   ```
   *(Để biết số `MIC_DEVICE_INDEX`, chạy lệnh: `python3 -c "import sounddevice as sd; print(sd.query_devices())"`)*.

3. **Lệnh khởi động MagicMirror trên Linux**:
   Trên Linux, dùng lệnh tiêu chuẩn:
   ```bash
   npm run start
   ```
   *(thay vì `npm.cmd run start:windows` như trên Windows)*.

### 6. Cấu Hình Tự Động Khởi Động Khi Bật Nguồn Pi (Autostart PM2)
Để khi cắm điện cho Raspberry Pi 5, MagicMirror và Backend AI tự động chạy toàn màn hình mà không cần mở Terminal:

1. Cài đặt PM2:
   ```bash
   sudo npm install -g pm2
   pm2 startup
   ```
   *(Chạy lệnh `sudo env PATH=...` theo hướng dẫn hiện ra trên màn hình)*.

2. Tạo script chạy Backend:
   Tạo file `start_backend.sh`:
   ```bash
   #!/bin/bash
   cd ~/MagicMirror-master
   source venv/bin/activate
   python cli_controller.py
   ```
   Cấp quyền thực thi: `chmod +x start_backend.sh`

3. Đăng ký tiến trình vào PM2:
   ```bash
   pm2 start start_backend.sh --name "mirror-backend"
   pm2 start npm --name "magicmirror" -- run start
   pm2 save
   ```
Bây giờ mỗi khi bạn cắm nguồn cho Raspberry Pi 5, Trợ lý AI và Gương thông minh sẽ tự động thức dậy và sẵn sàng nhận lệnh!

---

## 9. TỐI ƯU HÓA TÌM KIẾM ẢNH THỰC TẾ, PHÁT NHẠC ONLINE & GEMINI FLASH LITE

### 1. Tìm Kiếm Hình Ảnh Thực Tế Đa Nguồn (Wikipedia + Bing Images)
- Thay vì chỉ hiển thị một ảnh tháp Eiffel cố định, hệ thống đã tích hợp công cụ tìm kiếm ảnh thông minh:
  - Khi bạn nói: *"Cho tôi xem ảnh con mèo"*, *"Tìm ảnh hoa sen"*, *"Xem ảnh núi Phú Sĩ"*, v.v.
  - Hệ thống tự động truy vấn **Wikipedia Tiếng Việt** để lấy hình ảnh bách khoa độ phân giải cao và mở rộng qua **Bing Images**.
  - Không còn hiện tượng bị cố định vào một ảnh duy nhất.

### 2. Tự Động Tải & Caching Nhạc Trực Tuyến (`yt-dlp`)
- Khi bạn yêu cầu bài hát không có sẵn trong thư mục máy:
  - Hệ thống tự động tìm kiếm trên YouTube qua `yt-dlp` và tải nhanh về thư mục [`modules/MMM-StateControl/music/`](file:///d:/magicMirror/MagicMirror-master/modules/MMM-StateControl/music/) (chỉ mất 2-3 giây).
  - Trình duyệt gương phát bài hát trực tiếp từ file nội bộ đã lưu, loại bỏ hoàn toàn lỗi **CORS**, lỗi chặn luồng Google Video hay link hết hạn.
  - Bài hát sẽ được lưu đệm cục bộ (caching) để lần sau bạn gọi lại sẽ phát tức thì mà không cần tải lại.

### 3. Mô Hình Gemini Flash Lite (Hạn Mức Miễn Phí Tối Đa)
- Đã cấu hình ưu tiên dòng mô hình **Gemini Flash Lite (`gemini-flash-lite-latest`, `gemini-3.5-flash-lite`)**:
  - Tốc độ phản hồi cực nhanh (< 0.6 giây).
  - Cung cấp hạn mức miễn phí (Free Tier) cao nhất từ Google AI Studio (lên tới 1.500 lượt gọi/ngày và 15-30 requests/phút), giúp gương thông minh hoạt động liên tục mà không bị lỗi giới hạn `429 RESOURCE_EXHAUSTED`.

---

## 10. COMPANION WEB HUB (BẢNG ĐIỀU KHIỂN WEB ĐA NĂNG & QUẢN LÝ THIẾT BỊ)

Đã tích hợp trọn vẹn ứng dụng web điều khiển hiện đại (`web/`) trực tiếp vào MagicMirror:

### 1. Các phân hệ trên Web Hub:
- **Quản lý thiết bị IoT (`/web` -> Mục Thiết Bị)**:
  - Cho phép người dùng tự thêm mới và xóa bất kỳ thiết bị IoT nào trong nhà (ESP32, đèn, quạt, máy lạnh, rèm...).
  - Mặc định danh sách trống (sạch sẽ, không gán sẵn thiết bị ảo).
  - Công tắc Bật/Tắt tức thì, hiển thị trạng thái On/Off, công suất tiêu thụ (W) và điện năng tích lũy (kWh).
- **Quản lý Lịch Cá Nhân (`/web` -> Mục Lịch Trình)**:
  - Hỗ trợ thêm nhiều link Google Calendar (.ics) cùng lúc.
  - Bộ lọc chọn lọc bật/tắt từng lịch trên danh sách.
  - Đồng bộ tự động với gương vật lý.
- **Kho Ảnh Snapshot & Mã QR (`/web` -> Mục Kho Ảnh)**:
  - Hiển thị toàn bộ ảnh chụp từ camera thật của gương trong `screen_shot/`.
  - Phân loại theo thẻ tag, tìm kiếm, xem ảnh phóng to kèm **Mã QR quét 1 giây để tải ảnh về điện thoại**.
- **Chế độ Sáng / Tối (Light & Dark Mode)**:
  - Chuyển đổi 1 chạm mượt mà giữa chế độ tối dịu mắt (OLED Night) và chế độ sáng thanh lịch (Clean Daylight).

### 2. Cách khởi động nhanh toàn bộ hệ sinh thái:
- **Trên Windows**:
  - Nhấp đúp vào file `start_all.bat`. File này sẽ tự động giải phóng port, biên dịch web nếu cần, chạy Python AI Backend và mở máy chủ MagicMirror.
- **Trên Raspberry Pi / Linux**:
  ```bash
  chmod +x start_all.sh
  ./start_all.sh
  ```
- **Địa chỉ truy cập**:
  - Giao diện Gương: `http://localhost:8080`
  - Web Hub (Điện thoại/PC): `http://localhost:8080/web` (hoặc `http://<IP_LAN_CUA_PI>:8080/web`)
  - WebSocket Bridge: `ws://localhost:8085`
  - Photo QR Download Server: `http://localhost:8086`

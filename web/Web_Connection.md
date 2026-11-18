# Web MagicMirror — chức năng và hướng dẫn kết nối Raspberry Pi

Tài liệu được đối chiếu với mã nguồn tại `D:\magicMirror\MagicMirror-master-main` ngày 18/11/2026. “PiOS” trong hướng dẫn được hiểu là **Raspberry Pi OS**. Giả định Pi đã có MagicMirror hoạt động và chỉ cần bổ sung web.

Phạm vi thực hiện yêu cầu này: chỉ tạo tài liệu `Web_Connection.md`. Các lệnh triển khai bên dưới là hướng dẫn để bạn tự chạy; chưa có file chương trình hay cấu hình nào được sửa, chưa kết nối hoặc cài đặt lên Pi.

## 1. Tóm tắt chức năng thực tế

Web nằm trong `web/`, dùng React + Vite + Tailwind CSS, có ba tab chính; hỗ trợ máy tính/điện thoại và đổi giao diện sáng/tối.

| Phần | Chức năng đã có | Giới hạn cần biết |
| --- | --- | --- |
| IoT | Thêm/xóa thiết bị, nhập tên/vị trí/loại/công suất; bật/tắt trạng thái; nạp 4 thiết bị mẫu; tính tổng W và kWh ước tính | Hiện chỉ thay đổi React state và `localStorage`, chưa gửi HTTP/WebSocket/MQTT đến ESP32. W/kWh là tính toán từ thông số nhập, không phải số đo cảm biến |
| Lịch | Thêm/xóa nhiều nguồn iCal `.ics`, đặt tên/màu, bật/tắt; xem sự kiện 7/14/30 ngày; tải lại mỗi 60 giây khi tab lịch đang mở; hiển thị giờ, địa điểm, mô tả | Cần API của Node MagicMirror, Internet và nguồn ICS hợp lệ. Bộ lọc ngoài màn hình lưu cục bộ; cần vào cài đặt và Lưu để gửi cấu hình lên máy chủ |
| Đồng bộ lịch | Lưu danh sách vào `data/calendars.json`; cấu hình gương và dịch vụ lịch Python hiện tại có đọc file này | Máy Pi phải có phần đọc lịch tương ứng. Đổi danh sách lịch có thể cần khởi động lại tiến trình Node để cấu hình gương được nạp lại |
| Thư viện ảnh | Đọc ảnh trong `screen_shot/`, tìm theo tên/ngày/nhãn, lọc nhãn, xem lớn, chuyển trước/sau, tải ảnh, sao chép liên kết và tạo QR | API Node hiện chỉ liệt kê file bắt đầu bằng `photo_`, đuôi `.jpg`, `.jpeg`, `.png` chữ thường. Phải làm mới để lấy ảnh mới |
| Xóa ảnh | Xóa ảnh trên ổ đĩa và file QR đi kèm nếu có | Đây là xóa file thật, không chỉ ẩn khỏi giao diện |

**Phân biệt với thiết kế dự kiến:** `web/PRODUCT.md` có mô tả mục tiêu điều khiển LED ESP32. Tuy nhiên luồng đang chạy là `App.jsx` → `IotView.jsx`; chưa có kết nối phần cứng. File `Esp32LedDeck.jsx` có giao diện màu/độ sáng/hiệu ứng nhưng chưa được gắn vào luồng này và cũng chưa tự gửi lệnh ra thiết bị.

Nút làm mới ở thanh điều hướng hiện tải lại **ảnh**, không đồng bộ toàn bộ IoT và lịch như thông báo trên giao diện có thể khiến người dùng hiểu.

## 2. Cách web kết nối với hệ thống

```text
Trình duyệt máy tính / điện thoại trong cùng mạng
          |
          v
http://IP_PI:8080/web/
          |
          +-- web/dist/                    Giao diện đã build
          +-- /api/photos                 Danh sách ảnh
          +-- /screen_shot/...            File ảnh thật
          +-- /api/calendars              Đọc / lưu danh sách lịch
          +-- /api/calendar/occurrences   Tính các lần xuất hiện, kể cả lịch lặp
          +-- /cors?url=...               Tải ICS qua máy chủ
```

| Cổng/địa chỉ trong bản mã hiện tại | Mục đích |
| --- | --- |
| `8080/` | Màn hình MagicMirror do Node phục vụ |
| `8080/web/` hoặc `8080/hub/` | Web quản lý đầy đủ, nên dùng địa chỉ này |
| `8085` | WebSocket Python phục vụ trợ lý và module gương; web hiện không trực tiếp điều khiển IoT qua cổng này |
| `8086` | Máy chủ ảnh/QR Python; có phục vụ web tĩnh và API ảnh nhưng chưa có các API lịch tương đương Node |
| `5173` mặc định | Vite khi phát triển; không cần chạy cổng này khi đã dùng `web/dist` trên 8080 |

Web gọi API bằng đường dẫn tương đối như `/api/photos`, vì vậy nên đặt giao diện và API trên **cùng IP, cùng cổng 8080**. Không mở `web/index.html` hoặc `web/dist/index.html` bằng cách nhấp đúp file.

**Quan trọng: chép riêng `web/` chỉ đủ khi MagicMirror bên Pi đã có các route/API tích hợp.** MagicMirror gốc hoặc bản cũ không tự nhận web quản lý chỉ vì có thêm thư mục.

## 3. Cần mang những gì sang Pi?

| File/thư mục | Khi nào cần |
| --- | --- |
| `web/` | Luôn cần; mang mã nguồn, `package.json`, `package-lock.json`, cấu hình Vite và `public/`. Có thể mang cả `dist/` đã build |
| `js/server.js` | Cần phần mount `/web`, `/hub`, ảnh và các API ảnh/lịch nếu Pi chưa có |
| `js/calendar_occurrences.js` | Cần cho endpoint `/api/calendar/occurrences`; bản này sử dụng `node-ical.expandRecurringEvent` |
| `js/server_functions.js` | Đối chiếu phần `/cors` nếu Pi thiếu proxy tải ICS hoặc xử lý URL không tương thích |
| `js/ip_access_control.js` | Đối chiếu vì `server.js` hiện import cả `ipAccessControl` và `socketIpAccessControl` |
| `js/main.js` | Đối chiếu listener `RELOAD` nếu muốn gương tự tải lại trang sau khi lưu lịch |
| `config/config.js` | Chỉ ghép cấu hình mạng, CORS và phần đọc `data/calendars.json`; giữ các module và cấu hình riêng trên Pi |
| `backend/services/calendar_service.py` | Chỉ cần đối chiếu nếu muốn trợ lý Python đọc danh sách lịch web; không cần để mở giao diện web trên 8080 |
| `screen_shot/` | Dùng thư mục trên Pi để lấy ảnh Pi chụp. Chỉ chép ảnh Windows nếu muốn mang cả ảnh cũ |
| `data/calendars.json` | Tùy chọn mang lịch cũ; không ghi đè lịch riêng đang có trên Pi. Có thể nhập lại bằng web |
| `package.json`, `package-lock.json` ở gốc | Đối chiếu phiên bản và dependency khi tích hợp server; không thay nguyên bộ chỉ để thêm web |

Không chuyển `node_modules`, môi trường Python `.MMenv`/`.venv`, `__pycache__` từ Windows sang Pi. Dependency cần cài theo Linux/ARM trên Pi; riêng `web/dist` là tài nguyên tĩnh nên có thể dùng bản build từ Windows.

Nếu hai máy khác phiên bản MagicMirror, hãy ghép các đoạn liên quan thay vì ghi đè toàn bộ file `js/` hoặc `config/`. `server.js` còn phụ thuộc cơ chế alias/import và các hàm của phiên bản MagicMirror bên Pi.

## 4. Chuẩn bị Raspberry Pi OS

Các ví dụ dưới dùng:

- Tài khoản trên Pi: `mirror` — thay bằng tài khoản thật, không mặc định luôn là `pi`.
- IP Pi: `192.168.1.50` — thay bằng IP thật.
- Thư mục MagicMirror: `/home/mirror/MagicMirror-master-main` — thay theo máy Pi.

Trên terminal của Pi:

```bash
whoami
hostname -I
cd /home/mirror/MagicMirror-master-main
pwd
node -v
npm -v
```

Máy Windows và Pi cần nhìn thấy nhau trong mạng. Nếu chép qua SSH/SCP, bật SSH bằng `sudo raspi-config`, tìm phần SSH trong Interface Options rồi bật. Raspberry Pi có tài liệu chính thức về [SSH và chuyển file](https://www.raspberrypi.com/documentation/computers/remote-access.html).

Nếu cần build trên Pi, kiểm tra Node theo dependency thực tế. `package.json` gốc trong bản này khai báo `>=22.21.1 <23 || >=24`; Node 24 là lựa chọn phù hợp để đối chiếu trước khi cài. Không nâng Node của hệ thống đang chạy một cách mù quáng; kiểm tra tương thích bản MagicMirror và package web trên Pi.

## 5. Kiểm tra Pi đã hỗ trợ web hay chưa

Chạy trên Pi, tại thư mục MagicMirror:

```bash
grep -nE 'webDistPath|/api/photos|/api/calendars|/api/calendar/occurrences' js/server.js
test -f js/calendar_occurrences.js && echo 'Có bộ xử lý lịch'
```

Nếu máy chủ đang chạy:

```bash
curl -i http://127.0.0.1:8080/api/photos
curl -i http://127.0.0.1:8080/api/calendars
```

- Có các route và API trả JSON: tiếp tục chép `web` rồi build/khởi động lại.
- Trả `404` hoặc thiếu route: phải tích hợp phần server ở mục 3 trước. Việc thêm `web` không tự bổ sung API.
- Lỗi kết nối: kiểm tra tiến trình MagicMirror, cổng và log trước khi kết luận thiếu API.

## 6. Chuyển từ Windows sang Pi

### 6.1. Đóng gói và gửi mã web

Chạy trong **PowerShell Windows**. Gói tạm được đặt trong thư mục TEMP, không gom `node_modules` và không gom `dist` cũ:

```powershell
Set-Location 'D:\magicMirror\MagicMirror-master-main'
$webArchive = Join-Path $env:TEMP 'magicmirror-web-source.tar.gz'
tar -czf $webArchive --exclude=web/node_modules --exclude=web/dist --exclude=web/.impeccable web
scp $webArchive mirror@192.168.1.50:/home/mirror/
```

Nếu Windows chưa có `scp`, có thể dùng WinSCP qua SFTP: chuyển các thành phần tương tự sang một thư mục tạm trên Pi; không chuyển `node_modules`.

### 6.2. Giải nén, sao lưu rồi đưa vào dự án

Chạy trên **Pi**:

```bash
mkdir -p /home/mirror/web-import
tar -xzf /home/mirror/magicmirror-web-source.tar.gz -C /home/mirror/web-import
cd /home/mirror/MagicMirror-master-main

# Nếu đã có web thì sao lưu trước khi chép đè.
if [ -d web ]; then
  cp -a web "web.backup-$(date +%Y%m%d-%H%M%S)"
fi
cp -a /home/mirror/web-import/web .
```

Nếu Pi thiếu tích hợp server, chuyển riêng các file tham chiếu ở mục 3 vào một thư mục tạm khác, so sánh bằng `diff -u`, sao lưu file đích rồi mới ghép phần cần thiết. Không thực hiện lệnh ghi đè server/config trước khi kiểm tra khác biệt. Tài liệu này chưa xác định phiên bản và nội dung thực tế bên Pi nên không coi việc thay nguyên file là bước bắt buộc.

### 6.3. Cài và build web trên Pi

```bash
cd /home/mirror/MagicMirror-master-main/web
npm ci --include=dev
npm run build
test -f dist/index.html && echo 'Build web hoàn tất'
```

Lệnh `npm ci` dùng lockfile của web; `--include=dev` bảo đảm có Vite để build kể cả khi môi trường đặt chế độ production. Nếu cài lỗi phiên bản Node hoặc lockfile, xử lý nguyên nhân trước; không xóa lockfile để thử ngẫu nhiên.

**Phương án Pi chỉ chạy, không build:** trên Windows chạy `npm ci --include=dev` và `npm run build` trong `web/`, sau đó chép nguyên `web/dist/` sang đúng `web/dist/` bên Pi. Khi dùng cách này, Pi không cần cài dependency frontend chỉ để phục vụ bản build; vẫn cần server/API tương thích và dependency Node của MagicMirror.

Khi tích hợp API lịch, kiểm tra dependency ở thư mục gốc:

```bash
cd /home/mirror/MagicMirror-master-main
npm ls node-ical
node -e 'console.log(typeof require("node-ical").expandRecurringEvent)'
```

Kết quả sau phải là `function`. Bản máy này khai báo `node-ical: ^0.26.1`; nếu Pi có bản thiếu hàm này thì cần cập nhật dependency phù hợp và kiểm tra tương thích. Không chạy `npm ci` ở gốc chỉ để cài web vì thao tác đó cài lại dependency của cả MagicMirror.

## 7. Cấu hình truy cập mạng và lịch

Chỉ khi cấu hình Pi chưa đáp ứng, sao lưu rồi sửa các trường tương ứng trong `config/config.js`. Đây là ví dụ cho mạng `192.168.1.x`, phải đổi subnet theo mạng thật:

```javascript
address: "0.0.0.0",
port: 8080,
basePath: "/",
ipWhitelist: ["127.0.0.1", "::1", "192.168.1.0/24"],
cors: "allowWhitelist",
corsDomainWhitelist: ["calendar.google.com"],
```

`address` quyết định nơi máy chủ lắng nghe, `ipWhitelist` quyết định máy nào được truy cập. Có thể tham khảo [cấu hình MagicMirror](https://docs.magicmirror.builders/configuration/introduction.html). Bản Windows hiện tại dùng `ipWhitelist: []`, tức cho phép mọi IP truy cập được tới máy chủ; ví dụ phía trên giới hạn theo mạng nhà.

Nếu dùng nguồn ICS từ tên miền khác, thêm đúng hostname vào `corsDomainWhitelist`. Tham số này cho phép proxy `/cors` tải nguồn lịch; không tự giải quyết mọi yêu cầu gửi POST giữa hai máy khác origin.

Để **lịch trên gương** đọc dữ liệu web, config Pi cần có logic đọc `data/calendars.json`, lọc các lịch `enabled !== false` và URL hợp lệ, rồi gán danh sách đó cho cấu hình module lịch. Xem đoạn đầu `config/config.js` và chỗ dùng `dynamicCalendars` trong bản máy này để ghép tương ứng.

Tài khoản chạy MagicMirror cần quyền đọc `web/dist`, đọc/xóa ảnh trong `screen_shot`, và ghi `data/calendars.json`. Nếu các thư mục chưa có:

```bash
mkdir -p screen_shot data
npm run config:check
```

Chạy các lệnh này tại thư mục gốc MagicMirror. Không cần chạy web bằng quyền root.

## 8. Khởi động và truy cập

Nếu MagicMirror đã được chạy bằng dịch vụ/systemd/PM2 hoặc cửa sổ gương hiện có, hãy khởi động lại **đúng tiến trình đó** sau khi thêm route hoặc build lần đầu. Không mở thêm một server thứ hai cùng cổng 8080.

Nếu chưa có tiến trình chạy, có thể kiểm tra web độc lập trong SSH:

```bash
cd /home/mirror/MagicMirror-master-main
node serveronly
```

Chế độ này phục vụ HTTP, không mở cửa sổ Electron và không tự khởi động Python AI/camera. Nếu cần gương vật lý, dùng cách khởi động gương đã hoạt động trên Pi; không cần chạy thêm Vite.

Mở từ điện thoại/máy tính:

```text
http://192.168.1.50:8080/web/
```

Dùng IP LAN thật ngay cả khi mở trình duyệt trên Pi nếu muốn quét QR bằng điện thoại. QR trong lightbox ghép từ `window.location.origin`; mở bằng `localhost` sẽ tạo liên kết `localhost` mà điện thoại không truy cập được.

`start_all.sh` hiện có thể khởi chạy Python và Electron nhưng cũng gọi `fuser -k` để dừng tiến trình trên các cổng 8080/8085/8086. Script chỉ build khi chưa có `web/dist/index.html`, nên không tự cập nhật một bản build cũ. Chỉ dùng script sau khi đã hiểu tác động và chuẩn bị đủ môi trường; cập nhật web thì chủ động build lại.

## 9. Thiết lập lịch và kiểm tra sau khi chuyển

1. Mở web bằng IP Pi, vào tab Lịch → Cài đặt.
2. Thêm URL iCal `.ics`, đặt tên/màu và bật lịch muốn dùng; không dán link trang giao diện Google Calendar thay cho ICS.
3. Nếu có trường địa chỉ Pi, nhập đúng `192.168.1.50:8080`. Quan trọng nhất là mở web trực tiếp trên origin của Pi để POST `/api/calendars` gửi về đúng máy.
4. Bấm Lưu, kiểm tra `GET /api/calendars` và file `data/calendars.json` trên Pi. Thông báo thành công của giao diện chưa đủ chứng minh máy chủ đã lưu vì mã hiện chưa kiểm tra HTTP status khi POST.
5. Nếu gương vẫn dùng danh sách lịch cũ, khởi động lại Node MagicMirror. `io.emit("RELOAD")` chỉ yêu cầu trình duyệt tải lại, không bảo đảm config Node được đọc lại từ ổ đĩa.
6. Với trợ lý giọng nói, xác nhận dịch vụ Python bên Pi có đọc cùng `data/calendars.json`; mã hiện tại phát hiện thay đổi file ở lần tải/đọc lịch tiếp theo.
7. Chụp một ảnh bằng luồng camera đang hoạt động trên Pi, làm mới tab Ảnh, thử xem lớn/tải và quét QR từ thiết bị khác. Chỉ thử xóa với ảnh không cần giữ.

Không nên dựa vào tùy chọn “đồng bộ sang IP Pi” khi vẫn mở web trên Windows: đoạn gửi từ xa đang dùng `mode: 'no-cors'` với JSON, nên không bảo đảm Express nhận và lưu đúng dữ liệu. Đặt web và API cùng trên Pi tránh phụ thuộc vào nhánh này.

Danh sách IoT và chủ đề giao diện lưu trong `localStorage` theo trình duyệt và origin. Đổi từ Windows sang IP Pi, đổi IP/cổng, hoặc dùng điện thoại khác sẽ không tự mang theo dữ liệu này. Danh sách lịch lưu trên máy chủ có thể tải lại; thiết bị IoT hiện cần nhập lại.

## 10. Lỗi thường gặp

| Hiện tượng | Kiểm tra / cách xử lý |
| --- | --- |
| Không truy cập được 8080 | Kiểm tra IP bằng `hostname -I`, tiến trình bằng `ss -ltnp`, `address`, whitelist; hai thiết bị cùng mạng và không bị Wi-Fi khách/client isolation. Nếu đã bật firewall thì kiểm tra rule cho TCP 8080 từ LAN |
| `/web/` trả 404 | Kiểm tra `web/dist/index.html`, mount trong `js/server.js`, khởi động lại Node sau khi thêm thư mục/build lần đầu |
| Trang trắng, asset 404 | Kiểm tra đã chép đủ `dist/assets`, dùng `/web/` có dấu `/` cuối và cấu hình Vite `base: './'`; tải lại trang không dùng cache |
| Giao diện mở nhưng ảnh/lịch lỗi | Kiểm tra `/api/photos`, `/api/calendars`, `/api/calendar/occurrences`; tránh dùng cổng 8086 cho toàn bộ web |
| `/api/photos` trả `[]` | Kiểm tra đúng thư mục `screen_shot` của dự án đang chạy, tên file và định dạng ảnh. Web không tự chụp ảnh và không tự tìm ảnh trên máy Windows |
| Lịch lỗi 403 qua `/cors` | Kiểm tra `cors`, hostname trong `corsDomainWhitelist`, URL hợp lệ; khởi động lại Node sau khi sửa config |
| Lịch lỗi 404 ở occurrences | Pi thiếu API mới hoặc chưa ghép `js/calendar_occurrences.js` |
| Lịch lỗi 422 / thiếu `expandRecurringEvent` | Kiểm tra nội dung ICS và phiên bản `node-ical` ở gốc |
| Lưu lịch báo thành công nhưng không có dữ liệu | Kiểm tra Network trong trình duyệt, HTTP status, quyền ghi `data/`, và xác nhận đang mở origin Pi |
| Quét QR không tải ảnh | QR phải chứa IP Pi mà điện thoại truy cập được; tránh `localhost`, IP cũ hoặc Wi-Fi khác mạng |
| Cập nhật source nhưng giao diện vẫn cũ | Chạy lại `npm run build` trong `web/`, chép đủ `dist`, tải lại không cache |
| Bật/tắt trên web mà ESP32 không đổi | Đây là giới hạn hiện tại: cần phát triển thêm API/giao thức điều khiển phần cứng |

## 11. Kết luận triển khai cho trường hợp này

Nếu MagicMirror trên Pi thật sự giống bản hiện tại và chỉ thiếu `web`, các bước chính là: **chép `web` → cài/build hoặc chuyển `dist` đã build → kiểm tra cấu hình LAN → khởi động lại MagicMirror → mở `http://IP_PI:8080/web/`**.

Nếu Pi chưa có route/API web, cần ghép thêm phần Node tương ứng; không cần chuyển lại toàn bộ Python AI chỉ để chạy web. Chưa thể xác nhận nhánh nào đúng nếu chưa đọc mã hoặc kiểm tra API bên Pi.

Web hiện chưa có cơ chế đăng nhập riêng; API có thể xóa ảnh và thay đổi lịch. Chỉ triển khai trong mạng tin cậy, không chuyển tiếp trực tiếp cổng này ra Internet. Giữ riêng tư URL iCal bí mật và file lịch có chứa URL đó.

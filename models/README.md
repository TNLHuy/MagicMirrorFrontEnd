# 🧠 THƯ MỤC LƯU TRỮ MÔ HÌNH TRÍ TUỆ NHÂN TẠO TẠI BIÊN (EDGE AI MODELS)

Thư mục này chứa các mô hình AI chạy trực tiếp 100% Offline trên Raspberry Pi 5 (8GB):

## 1. `wakeword/` (Mô hình nhận diện từ khóa openWakeWord)
- **Từ khóa**: `"Hey Mirror"`
- **Tệp mô hình**: `hey_mirror.onnx` (~773KB)
- **Kiến trúc**: openWakeWord (Audio Spectrogram Transformer / ONNX)
- **Đầu vào**: Khung xử lý 80ms (1280 samples @ 16kHz)
- **Ngưỡng kích hoạt**: `THRESHOLD = 0.35` (35%), `COOLDOWN = 1.8s`
- **Mục tiêu**: Lắng nghe liên tục 24/7 với tải CPU < 2%, phản hồi cực nhanh khi phát hiện từ khóa.

## 2. `stt/` (Mô hình nhận dạng giọng nói tiếng Việt tại biên)
- **Kích thước**: ~30M tham số (Mô hình Quantized INT8 / Q5_0).
- **Định dạng**: `.onnx` / `.bin` (Sherpa-ONNX Zipformer RNN-T 6000h).
- **Tốc độ mục tiêu**: ~0.3s cho đoạn âm thanh 10–12 giây trên 4 nhân ARM Cortex-A76 (ARM NEON).

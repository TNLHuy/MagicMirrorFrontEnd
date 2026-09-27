const WebSocket = require('ws');
const wss = new WebSocket.Server({ port: 8085 });

console.log("=========================================");
console.log("Mock WebSocket Server running on ws://localhost:8085");
console.log("=========================================");

// Sinh 1 giá trị biên độ "giống giọng nói thật": có nền dao động sin + nhiễu ngẫu nhiên,
// thỉnh thoảng chèn khoảng "nghỉ" (giữa các từ/câu) để không phải một đường đều đều.
function fakeVoiceAmplitude(tMs, { base = 0.35, noise = 0.5, pauseChance = 0.06 } = {}) {
    if (Math.random() < pauseChance) {
        return Math.random() * 0.08; // mô phỏng khoảng lặng giữa câu nói
    }
    const wave = Math.sin(tMs / 140) * 0.25 + Math.sin(tMs / 55) * 0.15;
    const jitter = (Math.random() - 0.5) * noise;
    const value = base + wave + jitter;
    return Math.max(0, Math.min(1, value));
}

// Bắn amplitude liên tục trong "durationMs", mỗi "intervalMs" một lần, rồi tự dừng.
// Trả về id của interval để có thể clearInterval() sớm nếu cần (vd server bị đóng giữa chừng).
function startAmplitudeStream(ws, durationMs, options, intervalMs = 80) {
    const startedAt = Date.now();
    const intervalId = setInterval(() => {
        const elapsed = Date.now() - startedAt;
        if (elapsed >= durationMs || ws.readyState !== WebSocket.OPEN) {
            clearInterval(intervalId);
            return;
        }
        const value = fakeVoiceAmplitude(elapsed, options);
        ws.send(JSON.stringify({ type: "amplitude", value: Number(value.toFixed(3)) }));
    }, intervalMs);
    return intervalId;
}

wss.on('connection', (ws) => {
    console.log('[+] MagicMirror đã kết nối thành công!');

    ws.send(JSON.stringify({ state: 0 }));

    const startCycle = () => {
        // t=3s -> State 2, sub-state "listening" (chờ, chưa ai nói, amplitude thấp/tĩnh)
        setTimeout(() => {
            console.log("--> State 2 / listening");
            ws.send(JSON.stringify({
                state: 2,
                subState: "listening",
                text: "Tôi đang nghe bạn..."
            }));
        }, 3000);

        // t=4s -> Người dùng bắt đầu nói: đổi sub-state + bắn amplitude thật liên tục trong 4s
        setTimeout(() => {
            console.log("--> State 2 / user_speaking (đang giả lập amplitude...)");
            ws.send(JSON.stringify({
                state: 2,
                subState: "user_speaking"
            }));
            startAmplitudeStream(ws, 4000, { base: 0.4, noise: 0.6, pauseChance: 0.08 });
        }, 4000);

        // t=8.5s -> AI trả lời: đổi text + sub-state + bắn amplitude kiểu khác (giọng AI đều hơn) trong 4.5s
        setTimeout(() => {
            console.log("--> State 2 / ai_responding (đang giả lập amplitude...)");
            ws.send(JSON.stringify({
                state: 2,
                subState: "ai_responding",
                text: "Bây giờ là 20:00, thời tiết TP.HCM rất mát mẻ."
            }));
            startAmplitudeStream(ws, 4500, { base: 0.45, noise: 0.35, pauseChance: 0.03 });
        }, 8500);

        // t=14s -> Hiện lại Widget (State 1)
        setTimeout(() => {
            console.log("--> State 1: Ambient Display");
            ws.send(JSON.stringify({ state: 1 }));
        }, 14000);

        // t=20s -> Về Sleep (State 0)
        setTimeout(() => {
            console.log("--> State 0: Sleep Standby");
            ws.send(JSON.stringify({ state: 0 }));
        }, 20000);
    };

    startCycle();
    setInterval(startCycle, 22000);
});
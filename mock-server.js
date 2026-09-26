const WebSocket = require('ws');
const wss = new WebSocket.Server({ port: 8085 });

console.log("=========================================");
console.log("Mock WebSocket Server running on ws://localhost:8085");
console.log("=========================================");

wss.on('connection', (ws) => {
    console.log('[+] MagicMirror đã kết nối thành công!');

    // Bắt đầu ở State 0 (Tắt màn hình)
    ws.send(JSON.stringify({ state: 0 }));

    const startCycle = () => {
        // Sau 3s -> Chuyển sang State 2 (Đang lắng nghe)
        setTimeout(() => {
            console.log("--> State 2: Lắng nghe...");
            ws.send(JSON.stringify({ 
                state: 2, 
                text: "Tôi đang nghe bạn..." 
            }));
        }, 3000);

        // Sau 8s -> AI xử lý xong và Trả lời (Vẫn ở State 2 nhưng đổi chữ)
        setTimeout(() => {
            console.log("--> State 2: AI Trả lời");
            ws.send(JSON.stringify({ 
                state: 2, 
                text: "Bây giờ là 20:00, thời tiết TP.HCM rất mát mẻ." 
            }));
        }, 8000);

        // Sau 14s -> Hiện lại các Widget (State 1)
        setTimeout(() => {
            console.log("--> State 1: Ambient Display");
            ws.send(JSON.stringify({ state: 1 }));
        }, 14000);

        // Sau 20s -> Quay về State 0 (Sleep)
        setTimeout(() => {
            console.log("--> State 0: Sleep Standby");
            ws.send(JSON.stringify({ state: 0 }));
        }, 20000);
    };

    startCycle();
    setInterval(startCycle, 22000);
});
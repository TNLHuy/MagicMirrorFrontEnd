/**
 * ====================================================================
 *   SOCKET CLIENT (WEBSOCKET REALTIME DISPATCHER)
 *   Quản lý kết nối WebSocket với backend Python, tự động kết nối lại (auto-reconnect),
 *   phân loại và điều phối các gói tin Action, Amplitude, State.
 * ====================================================================
 */
class SocketClient {
    constructor(url = "ws://localhost:8085", callbacks = {}) {
        this.url = url;
        this.callbacks = callbacks;
        this.socket = null;
        this.reconnectTimer = null;
        this.isExplicitClose = false;
    }

    connect() {
        const self = this;
        this.isExplicitClose = false;

        try {
            const socket = new WebSocket(this.url);
            this.socket = socket;

            socket.onopen = function () {
                if (typeof Log !== "undefined") {
                    Log.info("[SocketClient] Kết nối WebSocket Backend thành công tại: " + self.url);
                }
                if (self.callbacks.onOpen) self.callbacks.onOpen();
            };

            socket.onmessage = function (event) {
                try {
                    const data = JSON.parse(event.data);

                    // 1. Gói tin biên độ âm thanh RMS thời gian thực
                    if (data.type === "amplitude" || typeof data.amplitude !== "undefined") {
                        const val = data.value !== undefined ? data.value : data.amplitude;
                        if (self.callbacks.onAmplitude) self.callbacks.onAmplitude(val);
                        return;
                    }

                    // 2. Gói tin Action theo NLU Router (10 ACTIONS)
                    if (data.action) {
                        if (self.callbacks.onAction) self.callbacks.onAction(data);
                        return;
                    }

                    // 3. Gói tin State (0: Sleep, 1: Active)
                    if (typeof data.state !== "undefined") {
                        const stateNum = Number(data.state);
                        const subState = data.subState || data.sub_state || null;
                        const text = data.text || null;
                        if (self.callbacks.onState) self.callbacks.onState(stateNum, text, subState);
                    }
                } catch (e) {
                    if (typeof Log !== "undefined") {
                        Log.error("[SocketClient] Lỗi phân tích cú pháp WebSocket JSON:", e);
                    }
                }
            };

            socket.onclose = function () {
                if (typeof Log !== "undefined") {
                    Log.warn("[SocketClient] Mất kết nối WebSocket. Thử kết nối lại sau 3s...");
                }
                if (self.callbacks.onClose) self.callbacks.onClose();

                if (!self.isExplicitClose) {
                    clearTimeout(self.reconnectTimer);
                    self.reconnectTimer = setTimeout(function () {
                        self.connect();
                    }, 3000);
                }
            };

            socket.onerror = function (error) {
                if (typeof Log !== "undefined") {
                    Log.error("[SocketClient] WebSocket Error:", error);
                }
                if (self.callbacks.onError) self.callbacks.onError(error);
            };
        } catch (err) {
            if (typeof Log !== "undefined") {
                Log.error("[SocketClient] Ngoại lệ khi tạo WebSocket:", err);
            }
        }
    }

    send(payload) {
        if (this.socket && this.socket.readyState === WebSocket.OPEN) {
            try {
                this.socket.send(JSON.stringify(payload));
                return true;
            } catch (err) {
                if (typeof Log !== "undefined") {
                    Log.error("[SocketClient] Lỗi gửi tin nhắn qua WebSocket:", err);
                }
                return false;
            }
        } else {
            if (typeof Log !== "undefined") {
                Log.warn("[SocketClient] WebSocket chưa mở, không thể gửi tin nhắn.");
            }
            return false;
        }
    }

    close() {
        this.isExplicitClose = true;
        clearTimeout(this.reconnectTimer);
        if (this.socket) {
            this.socket.close();
            this.socket = null;
        }
    }
}

if (typeof window !== "undefined") {
    window.SocketClient = SocketClient;
}

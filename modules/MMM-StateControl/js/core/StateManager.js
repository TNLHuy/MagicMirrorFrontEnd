/**
 * ====================================================================
 *   STATE MANAGER (SYSTEM STATE & MAGICMIRROR VISIBILITY CONTROLLER)
 *   Điều phối trạng thái hệ thống:
 *   - State 0: Sleep / Standby (Màn hình gương đen, ẩn toàn bộ widget)
 *   - State 1: Active (Bật sáng gương, hiển thị 4 góc tĩnh, trợ lý sẵn sàng)
 *   - Quản lý trạng thái trợ lý ở bottom bar (idle, listening, thinking, speaking)
 * ====================================================================
 */
class StateManager {
    constructor(moduleInstance, options = {}) {
        this.moduleInstance = moduleInstance;
        this.lockString = options.lockString || "STATE_CONTROL_LOCK";
        this.animationSpeed = options.animationSpeed || 400;

        this.currentState = 0;            // 0: Sleep, 1: Active
        this.currentSubState = "idle";    // "idle" | "listening" | "user_speaking" | "thinking" | "speaking"

        // DOM elements
        this.masterContainerEl = null;
        this.bottomBarZoneEl = null;
        this.statusTextEl = null;
        this.bottomWave = null;
    }

    bindDom(elements = {}) {
        this.masterContainerEl = elements.masterContainerEl || document.getElementById("nlu-mirror-container");
        this.bottomBarZoneEl = elements.bottomBarZoneEl || document.getElementById("nlu-bottom-bar-zone");
        this.statusTextEl = elements.statusTextEl || document.getElementById("nlu-bottom-status-text");
        this.bottomWave = elements.bottomWave || null;
    }

    setBottomWave(wave) {
        this.bottomWave = wave;
    }

    /**
     * Chuyển đổi trạng thái hệ thống giữa State 0 (Sleep) và State 1 (Active)
     * @param {number} newState 0 hoặc 1
     * @param {string|null} textPayload Văn bản đi kèm nếu có
     * @param {string|null} subState Phân trạng thái trợ lý
     * @param {Function|null} onStateTransition Callback thông báo cho các component
     */
    setSystemState(newState, textPayload, subState, onStateTransition) {
        const self = this;
        let targetState = Number(newState);
        if (targetState === 2) targetState = 1;

        const isStateChange = targetState !== this.currentState;
        this.currentState = targetState;

        const otherModules = (typeof MM !== "undefined" && typeof this.moduleInstance !== "undefined")
            ? MM.getModules().exceptModule(this.moduleInstance)
            : null;

        if (targetState === 0) {
            // ================= STATE 0: SLEEP =================
            this.currentSubState = "idle";

            // Ẩn tất cả module tĩnh qua lockString của MagicMirror
            if (otherModules) {
                otherModules.enumerate(function (mod) {
                    mod.hide(self.animationSpeed, function () {}, { lockString: self.lockString });
                });
            }

            document.body.classList.add("state-sleep");
            document.body.classList.remove("state-active");

            if (this.bottomWave) {
                this.bottomWave.stop();
            }

            if (this.masterContainerEl) {
                this.masterContainerEl.classList.remove("visible");
            }

            if (onStateTransition) {
                onStateTransition(0);
            }

        } else if (targetState === 1) {
            // ================= STATE 1: ACTIVE =================
            if (isStateChange) {
                document.body.classList.remove("state-sleep");
                document.body.classList.add("state-active");

                // HIỆN TẤT CẢ WIDGET TĨNH (Đồng hồ, Thời tiết, Lịch)
                if (otherModules) {
                    otherModules.enumerate(function (mod) {
                        mod.show(self.animationSpeed, function () {}, { lockString: self.lockString });
                    });
                }
            }

            if (this.masterContainerEl) {
                this.masterContainerEl.classList.add("visible");
            }

            if (this.bottomWave && !this.bottomWave.running) {
                this.bottomWave.start();
            }

            if (onStateTransition) {
                onStateTransition(1, isStateChange);
            }

            if (subState) {
                this.updateAssistantStatus(subState, textPayload);
            } else if (isStateChange) {
                this.updateAssistantStatus("idle");
            }
        }

        if (typeof Log !== "undefined") {
            Log.info("[StateManager] System State = " + this.currentState);
        }
    }

    /**
     * Cập nhật trạng thái trợ lý AI ở thanh Bottom Bar
     * @param {"idle"|"listening"|"user_speaking"|"thinking"|"speaking"} status 
     * @param {string|null} text 
     */
    updateAssistantStatus(status, text) {
        this.currentSubState = status;
        if (!this.statusTextEl) return;

        if (status === "idle") {
            this.statusTextEl.textContent = text || "Sẵn sàng";
            if (this.bottomBarZoneEl) this.bottomBarZoneEl.className = "nlu-bottom-bar-zone status-idle";
            if (this.bottomWave) this.bottomWave.setAmplitude(0.05);
        } else if (status === "listening") {
            this.statusTextEl.textContent = text || "Đang lắng nghe...";
            if (this.bottomBarZoneEl) this.bottomBarZoneEl.className = "nlu-bottom-bar-zone status-listening";
            if (this.bottomWave) this.bottomWave.setAmplitude(0.20);
        } else if (status === "user_speaking") {
            this.statusTextEl.textContent = text || "Đang nhận dạng giọng nói...";
            if (this.bottomBarZoneEl) this.bottomBarZoneEl.className = "nlu-bottom-bar-zone status-speaking";
        } else if (status === "thinking") {
            this.statusTextEl.textContent = text || "Đang xử lý câu hỏi...";
            if (this.bottomBarZoneEl) this.bottomBarZoneEl.className = "nlu-bottom-bar-zone status-thinking";
        } else if (status === "speaking") {
            this.statusTextEl.textContent = text || "Trợ lý đang phản hồi...";
            if (this.bottomBarZoneEl) this.bottomBarZoneEl.className = "nlu-bottom-bar-zone status-responding";
            if (this.bottomWave) this.bottomWave.setAmplitude(0.25);
        }
    }
}

if (typeof window !== "undefined") {
    window.StateManager = StateManager;
}

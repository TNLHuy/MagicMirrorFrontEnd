/**
 * ====================================================================
 *                 MMM-StateControl (MagicMirror2)
 *                 BỐ CỤC KHÔNG GIAN NLU ROUTER (MODULAR ORCHESTRATOR)
 * ====================================================================
 * - State 0: Sleep / Standby (Màn hình tắt đen, ẩn toàn bộ widget)
 * - State 1: Active Display:
 *     + MODULE TĨNH (Cố định ở 4 góc):
 *         [TOP_LEFT]     : Đồng hồ số & Thứ Ngày (clock) -> GET_TIME, GET_DATE
 *         [TOP_RIGHT]    : Thời tiết hiện tại (weather)   -> SHOW_WEATHER
 *         [BOTTOM_LEFT]  : Lịch trình cá nhân (calendar) -> GET_CALENDAR
 *         [BOTTOM_RIGHT] : Trình phát nhạc mini (PLAY_MEDIA) & Trạng thái SmartHome (SMART_HOME)
 *     + MODULE ĐỘNG:
 *         [MIDDLE_CENTER]: Khu vực hiển thị tương tác (Popup / Overlay khi có voice action):
 *             • NONE          : Bong bóng phụ AI hội thoại (response_text)
 *             • SEARCH (img)  : Popup ảnh toàn màn hình / modal web image
 *             • SEARCH (cam)  : Phân tích đồ vật + Vision tag
 *             • TAKE_PHOTO    : Đếm ngược 3-2-1 + Xem trước ảnh vừa chụp
 *         [BOTTOM_BAR]   : Thanh trạng thái trợ lý: [Đang nghe...] / [Volume] (SYSTEM)
 * ====================================================================
 */

Module.register("MMM-StateControl", {
    defaults: {
        websocketUrl: "ws://localhost:8085",
        animationSpeed: 400,
        enableChime: true,
        enableTypewriter: true,
        autoHideDelay: 9000,
        assistantName: "Trợ lý AI"
    },

    // Sub-components & Helpers
    audioSynth: null,
    cameraMgr: null,
    socketClient: null,
    stateMgr: null,
    chatBubble: null,
    knowledgeCard: null,
    visionPopup: null,
    photoPreview: null,
    mediaPlayer: null,
    smartHome: null,
    scheduleWidget: null,
    bottomWave: null,

    // UI Element References
    masterContainerEl: null,
    volumeBarEl: null,
    volumeValEl: null,

    // Camera Flow State & Timers
    _isPhotoModeWaiting: false,
    _countdownInterval: null,
    _autoHideTimer: null,

    getHeader: function () {
        return "";
    },

    getStyles: function () {
        const resolve = (p) => (this.file ? this.file(p) : `modules/MMM-StateControl/${p}`);
        return [
            resolve("css/base.css"),
            resolve("css/camera.css"),
            resolve("css/popups.css"),
            resolve("css/widgets.css"),
            resolve("css/bottom-bar.css")
        ];
    },

    getScripts: function () {
        const resolve = (p) => (this.file ? this.file(p) : `modules/MMM-StateControl/${p}`);
        return [
            resolve("js/audio/SiriWaveVisualizer.js"),
            resolve("js/audio/AudioSynthesizer.js"),
            resolve("js/camera/CameraManager.js"),
            resolve("js/core/SocketClient.js"),
            resolve("js/core/StateManager.js"),
            resolve("js/components/ChatBubble.js"),
            resolve("js/components/KnowledgeCard.js"),
            resolve("js/components/VisionPopup.js"),
            resolve("js/components/PhotoPreview.js"),
            resolve("js/components/MediaPlayerWidget.js"),
            resolve("js/components/SmartHomeWidget.js"),
            resolve("js/components/ScheduleWidget.js")
        ];
    },

    start: function () {
        Log.info("[MMM-StateControl] Khởi tạo Orchestrator MMM-StateControl...");

        // Khởi tạo các module con
        this.audioSynth = new AudioSynthesizer(this.config.enableChime);
        this.cameraMgr = new CameraManager();
        this.chatBubble = new ChatBubble({
            assistantName: this.config.assistantName,
            enableTypewriter: this.config.enableTypewriter
        });
        this.knowledgeCard = new KnowledgeCard();
        this.visionPopup = new VisionPopup();
        this.photoPreview = new PhotoPreview();
        this.mediaPlayer = new MediaPlayerWidget();
        this.smartHome = new SmartHomeWidget();
        this.scheduleWidget = new ScheduleWidget();
        this.stateMgr = new StateManager(this, {
            animationSpeed: this.config.animationSpeed
        });
    },

    notificationReceived: function (notification) {
        if (notification !== "DOM_OBJECTS_CREATED") return;

        // Binds DOM elements vào các component tương ứng
        this.masterContainerEl = document.getElementById("nlu-mirror-container");
        this.volumeBarEl = document.getElementById("nlu-bottom-volume-bar");
        this.volumeValEl = document.getElementById("nlu-bottom-volume-val");

        this.cameraMgr.bindDom();
        this.chatBubble.bindDom();
        this.knowledgeCard.bindDom();
        this.visionPopup.bindDom();
        this.photoPreview.bindDom();
        this.mediaPlayer.bindDom();
        this.smartHome.bindDom();
        this.scheduleWidget.bindDom();

        // Gắn cố định container vào body để điều phối toàn màn hình
        if (this.masterContainerEl && this.masterContainerEl.parentNode !== document.body) {
            document.body.appendChild(this.masterContainerEl);
        }

        // Khởi tạo Siri Wave Canvas ở bottom bar
        const waveHolder = document.getElementById("nlu-bottom-wave-holder");
        if (waveHolder && typeof BottomBarSiriWave !== "undefined") {
            this.bottomWave = new BottomBarSiriWave(waveHolder, { width: 380, height: 55 });
            this.bottomWave.start();
        }

        // Binds StateManager và kích hoạt trạng thái mặc định: State 0 (Sleep)
        this.stateMgr.bindDom({
            masterContainerEl: this.masterContainerEl,
            bottomBarZoneEl: document.getElementById("nlu-bottom-bar-zone"),
            statusTextEl: document.getElementById("nlu-bottom-status-text"),
            bottomWave: this.bottomWave
        });
        this.stateMgr.setSystemState(0);

        // Khởi tạo WebSocket kết nối Backend
        const self = this;
        this.socketClient = new SocketClient(this.config.websocketUrl, {
            onAmplitude: (val) => self.handleAmplitude(val),
            onAction: (data) => self.handleNluAction(data),
            onState: (stateNum, text, subState) => {
                self.stateMgr.setSystemState(stateNum, text, subState, (targetState) => {
                    if (targetState === 0) {
                        self.hideAllPopups();
                        self.mediaPlayer.stop();
                        if (self.scheduleWidget) self.scheduleWidget.hide();
                    }
                });
            }
        });
        this.socketClient.connect();
    },

    handleAmplitude: function (value) {
        if (this.stateMgr.currentState !== 1) return;
        const val = Math.max(0.0, Math.min(1.0, Number(value) || 0));

        if (this.bottomWave) {
            this.bottomWave.setAmplitude(val);
        }

        if (this.volumeBarEl) {
            const pct = Math.round(val * 100);
            this.volumeBarEl.style.width = Math.max(8, pct) + "%";
            if (this.volumeValEl) {
                this.volumeValEl.textContent = pct + "%";
            }
        }

        if (this.stateMgr.currentSubState === "listening" && val > 0.06) {
            this.stateMgr.updateAssistantStatus("user_speaking");
        }
    },

    /**
     * XỬ LÝ 10 ACTIONS NLU ROUTER
     */
    handleNluAction: function (data) {
        const action = (data.action || "").toUpperCase();

        // Luôn chuyển sang State 1 khi có tương tác người dùng
        if (this.stateMgr.currentState !== 1) {
            this.stateMgr.setSystemState(1);
        }

        if (action === "NONE" || action === "SPEAK" || action === "CHAT") {
            const text = data.response_text || data.text || "Tôi có thể giúp gì cho bạn?";
            // Khi camera đang mở chờ tạo dáng hoặc đang đếm ngược: hiển thị vào status bar, KHÔNG tắt camera!
            if (this.cameraMgr.isActive || this._isPhotoModeWaiting || this._countdownInterval) {
                this.stateMgr.updateAssistantStatus("speaking", text);
                return;
            }
            this.hideAllPopups();
            this.chatBubble.show(text);
            this.stateMgr.updateAssistantStatus("speaking");

            // Câu thoại ngắn (< 50 ký tự) như xác nhận đơn giản: 4.5s là vừa đủ; câu dài mới giữ 8s
            const delay = (text.length < 50) ? 4500 : (this.config.autoHideDelay || 8000);
            this.startAutoHideTimer(delay);

        } else if (action === "SEARCH") {
            const target = (data.target || "web_image").toLowerCase();
            if (target === "web_image" || target === "image") {
                this.hideAllPopups();
                this.knowledgeCard.show(data);
                this.stateMgr.updateAssistantStatus("speaking");
                this.startAutoHideTimer(16000);
            } else if (target === "camera" || target === "vision" || target === "object") {
                this.startVisionScanSequence(data);
            }

        } else if (action === "VISION_RESULT") {
            this.hideAllPopups();
            this.visionPopup.show(data);
            this.stateMgr.updateAssistantStatus("idle", "👁️ Đã nhận diện vật thể");
            this.startAutoHideTimer(11000);

        } else if (action === "OPEN_PHOTO_PREVIEW") {
            this.openPhotoModePreview(data);

        } else if (action === "START_PHOTO_COUNTDOWN") {
            const countdown = data.countdown || 3;
            this.startPhotoCountdownSequence(countdown);

        } else if (action === "CANCEL_PHOTO") {
            this.cancelPhotoMode();

        } else if (action === "TAKE_PHOTO") {
            if (data.immediate) {
                const countdown = data.countdown || 3;
                this.startPhotoCountdownSequence(countdown);
            } else {
                this.openPhotoModePreview(data);
            }

        } else if (action === "PHOTO_CAPTURED") {
            this.photoPreview.showCaptured(data.image_url, data.filename);
            this.stateMgr.updateAssistantStatus("idle", "Đã lưu ảnh vào: screen_shot/" + (data.filename || ""));
            this.startAutoHideTimer(14000);

        } else if (action === "PLAY_MEDIA") {
            this.mediaPlayer.update(data);
            if (data.response_text) {
                this.chatBubble.show(data.response_text);
                this.stateMgr.updateAssistantStatus("speaking");
                // Câu lệnh điều khiển nhạc đơn giản: Ẩn bong bóng nhanh sau 4 giây
                this.startAutoHideTimer(4000);
            }

        } else if (action === "SMART_HOME") {
            this.smartHome.update(data);
            if (data.response_text) {
                this.chatBubble.show(data.response_text);
                this.stateMgr.updateAssistantStatus("speaking");
                // Câu lệnh điều khiển nhà thông minh đơn giản: Ẩn bong bóng nhanh sau 4 giây
                this.startAutoHideTimer(4000);
            }

        } else if (action === "GET_CALENDAR") {
            this.hideAllPopups();
            this.scheduleWidget.update(data);
            if (data.response_text) {
                this.chatBubble.show(data.response_text);
                this.stateMgr.updateAssistantStatus("speaking");
                this.startAutoHideTimer(14000);
            }

        } else if (action === "LISTEN" || action === "LISTENING") {
            if (!this.cameraMgr.isActive && !this._isPhotoModeWaiting && !this._countdownInterval) {
                this.hideAllPopups();
            }
            this.stateMgr.updateAssistantStatus("listening", data.text || "Đang lắng nghe...");
            this.audioSynth.playWakeChime();

        } else if (action === "THINK" || action === "THINKING") {
            this.stateMgr.updateAssistantStatus("thinking", data.text || "Đang xử lý câu hỏi...");

        } else if (action === "IDLE") {
            if (!this.cameraMgr.isActive && !this._isPhotoModeWaiting && !this._countdownInterval) {
                this.hideAllPopups();
            }
            this.stateMgr.updateAssistantStatus("idle");

        } else if (action === "SYSTEM") {
            if (data.state !== undefined) {
                this.stateMgr.setSystemState(Number(data.state), null, null, (targetState) => {
                    if (targetState === 0) {
                        this.hideAllPopups();
                        this.mediaPlayer.stop();
                    }
                });
            }
            if (data.volume !== undefined) {
                this.handleAmplitude(Number(data.volume));
            }
        }
    },

    // -------------------------------------------------------------
    // CAMERA FLOWS (PHOTO PREVIEW, COUNTDOWN, VISION SCANNER)
    // -------------------------------------------------------------

    openPhotoModePreview: async function (data) {
        this.clearAutoHideTimer();
        this.hideAllPopups(true);

        const cameraStarted = await this.cameraMgr.startPreview("photo");
        if (!cameraStarted) {
            Log.error("[MMM-StateControl] Không thể mở webcam cho preview chụp ảnh.");
            return;
        }

        this._isPhotoModeWaiting = true;
        this.cameraMgr.setPosingHintVisible(true);

        const textMsg = (data && (data.text || data.response_text)) || "Đang chờ tạo dáng... Nói 'Chụp ảnh' để chụp, hoặc 'Hủy' để thoát";
        this.stateMgr.updateAssistantStatus("listening", textMsg);
    },

    startPhotoCountdownSequence: function (countdownSeconds) {
        this.clearAutoHideTimer();
        this._isPhotoModeWaiting = false;

        let currentCount = Number(countdownSeconds) || 3;
        this.cameraMgr.showCountdown(currentCount);
        this.audioSynth.playCountdownBeep(currentCount);
        this.stateMgr.updateAssistantStatus("thinking", `📸 Chuẩn bị... Chụp sau ${currentCount}s`);

        if (this._countdownInterval) {
            clearInterval(this._countdownInterval);
        }

        this._countdownInterval = setInterval(() => {
            currentCount--;
            if (currentCount > 0) {
                this.cameraMgr.showCountdown(currentCount);
                this.audioSynth.playCountdownBeep(currentCount);
                this.stateMgr.updateAssistantStatus("thinking", `📸 Tạo dáng nào! Chụp sau ${currentCount}s`);
            } else {
                clearInterval(this._countdownInterval);
                this._countdownInterval = null;

                // Phát âm thanh cơ học màn trập & chớp flash máy ảnh
                this.audioSynth.playShutterSound();
                this.cameraMgr.triggerFlash();

                // Chụp frame trực tiếp từ camera live preview
                const capturedDataUrl = this.cameraMgr.captureFrame();

                // Đóng camera live preview
                this.cameraMgr.stopPreview();

                if (capturedDataUrl) {
                    // Gửi ảnh chụp lên backend Python để lưu vào thư mục screen_shot/
                    this.socketClient.send({
                        action: "CLIENT_PHOTO_CAPTURED",
                        data_url: capturedDataUrl
                    });

                    // Hiển thị ngay ảnh vừa chụp ở MIDDLE_CENTER
                    this.photoPreview.showCaptured(capturedDataUrl);
                    this.stateMgr.updateAssistantStatus("idle", "📸 Đã chụp ảnh thành công!");
                    this.startAutoHideTimer(14000);
                }
            }
        }, 1000);
    },

    cancelPhotoMode: function () {
        this.clearAutoHideTimer();
        this._isPhotoModeWaiting = false;
        if (this._countdownInterval) {
            clearInterval(this._countdownInterval);
            this._countdownInterval = null;
        }
        this.cameraMgr.stopPreview();
        this.stateMgr.updateAssistantStatus("idle", "Đã hủy chế độ chụp ảnh");
    },

    startVisionScanSequence: async function (data) {
        this.hideAllPopups();

        const cameraStarted = await this.cameraMgr.startPreview("vision");
        this.stateMgr.updateAssistantStatus("thinking", "👁️ Giữ yên đồ vật trước gương để AI quét...");

        // Quét đồ vật trong 3.5 giây cho người dùng căn chỉnh góc nhìn
        setTimeout(() => {
            let capturedDataUrl = null;
            if (cameraStarted) {
                capturedDataUrl = this.cameraMgr.captureFrame();
            }

            this.cameraMgr.stopPreview();

            if (capturedDataUrl) {
                // Hiển thị khung kết quả ở MIDDLE_CENTER với ảnh vừa quét và trạng thái loading
                this.visionPopup.showLoading(capturedDataUrl);
                this.stateMgr.updateAssistantStatus("thinking", "Đang nhận diện vật thể qua Gemini Vision...");

                // Gửi frame lên backend Python để phân tích qua Gemini Vision
                this.socketClient.send({
                    action: "CLIENT_VISION_FRAME",
                    data_url: capturedDataUrl
                });
            } else {
                Log.warn("[MMM-StateControl] Không thể lấy frame từ camera live feed.");
            }
        }, 3500);
    },

    // -------------------------------------------------------------
    // POPUPS & AUTO-HIDE MANAGEMENT
    // -------------------------------------------------------------

    hideAllPopups: function (preserveCamera = false) {
        this.chatBubble.hide();
        this.knowledgeCard.hide();
        this.visionPopup.hide();
        this.photoPreview.hide();
        if (this.scheduleWidget) {
            this.scheduleWidget.hide();
        }

        if (!preserveCamera) {
            if (this._countdownInterval) {
                clearInterval(this._countdownInterval);
                this._countdownInterval = null;
            }
            this._isPhotoModeWaiting = false;
            this.cameraMgr.stopPreview();
        }
    },

    startAutoHideTimer: function (customDelay) {
        this.clearAutoHideTimer();
        const delay = customDelay || this.config.autoHideDelay || 9000;
        this._autoHideTimer = setTimeout(() => {
            if (this.cameraMgr.isActive || this._isPhotoModeWaiting || this._countdownInterval) {
                return;
            }
            this.hideAllPopups();
            this.stateMgr.updateAssistantStatus("idle");
        }, delay);
    },

    clearAutoHideTimer: function () {
        if (this._autoHideTimer) {
            clearTimeout(this._autoHideTimer);
            this._autoHideTimer = null;
        }
    },

    // -------------------------------------------------------------
    // DOM ASSEMBLY
    // -------------------------------------------------------------

    getDom: function () {
        if (!this.cameraMgr) {
            this.start();
        }

        const wrapper = document.createElement("div");
        wrapper.id = "nlu-mirror-container";
        wrapper.className = "nlu-mirror-container";

        // Flash máy ảnh
        wrapper.appendChild(this.cameraMgr.createFlashDom());

        // Fullscreen Camera Overlay (Gương soi toàn màn hình)
        wrapper.appendChild(this.cameraMgr.createDom());

        // MIDDLE_CENTER ZONE (Popups tương tác)
        const middleZone = document.createElement("div");
        middleZone.id = "nlu-middle-center-zone";
        middleZone.className = "nlu-middle-center-zone";
        middleZone.appendChild(this.chatBubble.createDom());
        middleZone.appendChild(this.knowledgeCard.createDom());
        middleZone.appendChild(this.visionPopup.createDom());
        middleZone.appendChild(this.photoPreview.createDom());
        wrapper.appendChild(middleZone);

        // BOTTOM_RIGHT ZONE (Widgets phụ)
        const bottomRightZone = document.createElement("div");
        bottomRightZone.id = "nlu-bottom-right-zone";
        bottomRightZone.className = "nlu-bottom-right-zone";
        bottomRightZone.appendChild(this.mediaPlayer.createDom());
        bottomRightZone.appendChild(this.smartHome.createDom());
        bottomRightZone.appendChild(this.scheduleWidget.createDom());
        wrapper.appendChild(bottomRightZone);

        // BOTTOM_BAR ZONE (Thanh trạng thái trợ lý AI)
        const bottomBarZone = document.createElement("div");
        bottomBarZone.id = "nlu-bottom-bar-zone";
        bottomBarZone.className = "nlu-bottom-bar-zone status-idle";
        bottomBarZone.innerHTML = `
            <div class="bottom-bar-left">
                <span class="assistant-orb-pulse">✦</span>
                <span class="bottom-status-text" id="nlu-bottom-status-text">Sẵn sàng</span>
            </div>
            <div class="bottom-bar-center" id="nlu-bottom-wave-holder"></div>
            <div class="bottom-bar-right">
                <span class="volume-label">🔊 Âm lượng:</span>
                <div class="volume-meter-track">
                    <div class="volume-meter-fill" id="nlu-bottom-volume-bar" style="width: 25%;"></div>
                </div>
                <span class="volume-percent" id="nlu-bottom-volume-val">25%</span>
            </div>
        `;
        wrapper.appendChild(bottomBarZone);

        return wrapper;
    }
});
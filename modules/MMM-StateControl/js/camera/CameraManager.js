/**
 * ====================================================================
 *   CAMERA MANAGER (FULLSCREEN LIVE PREVIEW & FRAME CAPTURE)
 *   Quản lý luồng webcam trực tiếp, khung ngắm HUD, đếm ngược toàn màn hình,
 *   chế độ tạo dáng và chụp ảnh lật gương (Mirror Reflection).
 * ====================================================================
 */
class CameraManager {
    constructor() {
        this.stream = null;
        this.isActive = false;

        // DOM Elements
        this.overlayEl = null;
        this.videoEl = null;
        this.modeBadgeIcon = null;
        this.modeBadgeText = null;
        this.countdownBox = null;
        this.countValEl = null;
        this.posingHint = null;
        this.visionScanner = null;
        this.flashEl = null;
    }

    /**
     * Tạo cây DOM cho Fullscreen Camera Overlay
     * @returns {HTMLElement}
     */
    createDom() {
        const overlay = document.createElement("div");
        overlay.id = "nlu-fullscreen-camera-overlay";
        overlay.className = "nlu-fullscreen-camera-overlay";
        overlay.style.display = "none";
        overlay.innerHTML = `
            <video id="nlu-camera-video" class="camera-preview-video" autoplay playsinline muted></video>
            
            <!-- Viewfinder HUD Khung Ngắm Sci-Fi -->
            <div class="camera-hud-viewfinder">
                <div class="hud-corner top-left"></div>
                <div class="hud-corner top-right"></div>
                <div class="hud-corner bottom-left"></div>
                <div class="hud-corner bottom-right"></div>
                <div class="hud-center-crosshair"></div>
                <div class="hud-grid-lines"></div>
            </div>

            <!-- Huy hiệu chế độ camera -->
            <div class="camera-mode-badge" id="nlu-camera-mode-badge">
                <span class="badge-icon" id="nlu-camera-mode-icon">📸</span>
                <span class="badge-text" id="nlu-camera-mode-text">GƯƠNG SOI • ĐANG CHỜ TẠO DÁNG</span>
            </div>

            <!-- Bảng gợi ý giọng nói khi đang chờ tạo dáng (Interactive Posing State) -->
            <div class="camera-posing-hint" id="nlu-camera-posing-hint" style="display: none;">
                <div class="posing-hint-content">
                    <span class="posing-hint-icon">🎙️</span>
                    <div class="posing-hint-texts">
                        <span class="posing-hint-main">Nói <strong class="keyword-accent">"Chụp ảnh"</strong> hoặc <strong class="keyword-accent">"Bắt đầu"</strong> để đếm ngược</span>
                        <span class="posing-hint-sub">Nói <strong class="keyword-cancel">"Hủy"</strong> hoặc <strong class="keyword-cancel">"Thôi"</strong> để đóng camera</span>
                    </div>
                </div>
                <div class="posing-mic-pulse">
                    <span></span><span></span><span></span>
                </div>
            </div>

            <!-- Khung đếm ngược chụp ảnh toàn màn hình -->
            <div class="camera-photo-countdown" id="nlu-camera-fullscreen-countdown" style="display: none;">
                <div class="fullscreen-countdown-circle">
                    <span class="fullscreen-countdown-num" id="nlu-camera-fullscreen-count-val">3</span>
                </div>
                <div class="fullscreen-pose-tip">✨ Chuẩn bị tạo dáng trước gương ✨</div>
            </div>

            <!-- Khung quét laser nhận diện vật thể toàn màn hình -->
            <div class="camera-vision-scanner" id="nlu-camera-fullscreen-scanner" style="display: none;">
                <div class="laser-scanner-beam"></div>
                <div class="vision-target-reticle">
                    <div class="reticle-ring"></div>
                    <div class="reticle-pulse"></div>
                    <span class="reticle-label">GIỮ YÊN VẬT THỂ ĐỂ AI QUÉT</span>
                </div>
            </div>
        `;
        return overlay;
    }

    /**
     * Tạo DOM cho hiệu ứng flash chớp trắng
     * @returns {HTMLElement}
     */
    createFlashDom() {
        const flash = document.createElement("div");
        flash.id = "nlu-camera-flash";
        flash.className = "nlu-camera-flash";
        return flash;
    }

    /**
     * Gắn kết các phần tử DOM sau khi rendered
     */
    bindDom() {
        this.overlayEl = document.getElementById("nlu-fullscreen-camera-overlay");
        this.videoEl = document.getElementById("nlu-camera-video");
        this.modeBadgeIcon = document.getElementById("nlu-camera-mode-icon");
        this.modeBadgeText = document.getElementById("nlu-camera-mode-text");
        this.countdownBox = document.getElementById("nlu-camera-fullscreen-countdown");
        this.countValEl = document.getElementById("nlu-camera-fullscreen-count-val");
        this.posingHint = document.getElementById("nlu-camera-posing-hint");
        this.visionScanner = document.getElementById("nlu-camera-fullscreen-scanner");
        this.flashEl = document.getElementById("nlu-camera-flash");
    }

    /**
     * Bật live stream camera chế độ fullscreen
     * @param {"photo"|"vision"} mode Chế độ camera
     * @returns {Promise<boolean>}
     */
    async startPreview(mode = "photo") {
        try {
            if (this.stream) {
                this.stopPreview();
            }

            const videoConstraints = {
                video: {
                    width: { ideal: 1920 },
                    height: { ideal: 1080 },
                    facingMode: "user"
                },
                audio: false
            };

            let stream = null;
            try {
                stream = await navigator.mediaDevices.getUserMedia(videoConstraints);
            } catch (err) {
                if (typeof Log !== "undefined") {
                    Log.warn("[CameraManager] Mở webcam với độ phân giải mặc định do:", err);
                }
                stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
            }

            this.stream = stream;
            this.isActive = true;

            if (this.videoEl) {
                this.videoEl.srcObject = stream;
                try {
                    await this.videoEl.play();
                } catch (pe) {
                    if (typeof Log !== "undefined") {
                        Log.warn("[CameraManager] Không thể tự động play video:", pe);
                    }
                }
            }

            this.setMode(mode);

            if (this.overlayEl) {
                this.overlayEl.style.display = "block";
                this.overlayEl.classList.add("active");
            }

            // Ẩn tất cả widget khác, chỉ chừa bottom AI bar
            document.body.classList.add("camera-fullscreen-active");

            return true;
        } catch (e) {
            if (typeof Log !== "undefined") {
                Log.error("[CameraManager] Không thể mở webcam:", e);
            }
            this.stopPreview();
            return false;
        }
    }

    /**
     * Cài đặt chế độ hiển thị trên HUD camera
     * @param {"photo"|"vision"} mode
     */
    setMode(mode) {
        if (mode === "photo") {
            if (this.modeBadgeIcon) this.modeBadgeIcon.textContent = "📸";
            if (this.modeBadgeText) this.modeBadgeText.textContent = "GƯƠNG SOI CHỤP ẢNH • TẠO DÁNG";
            if (this.countdownBox) this.countdownBox.style.display = "none";
            if (this.visionScanner) this.visionScanner.style.display = "none";
            if (this.posingHint) this.posingHint.style.display = "flex";
        } else if (mode === "vision") {
            if (this.modeBadgeIcon) this.modeBadgeIcon.textContent = "👁️";
            if (this.modeBadgeText) this.modeBadgeText.textContent = "AI VISION SCANNER • QUÉT ĐỒ VẬT";
            if (this.countdownBox) this.countdownBox.style.display = "none";
            if (this.posingHint) this.posingHint.style.display = "none";
            if (this.visionScanner) this.visionScanner.style.display = "block";
        }
    }

    /**
     * Cập nhật trạng thái hiển thị gợi ý giọng nói khi tạo dáng
     * @param {boolean} visible
     */
    setPosingHintVisible(visible) {
        if (this.posingHint) {
            this.posingHint.style.display = visible ? "flex" : "none";
        }
    }

    /**
     * Hiển thị số đếm ngược trên camera fullscreen với animation bounce
     * @param {number} count Số đếm
     */
    showCountdown(count) {
        if (this.posingHint) this.posingHint.style.display = "none";
        if (this.countdownBox) this.countdownBox.style.display = "flex";
        if (this.modeBadgeText) this.modeBadgeText.textContent = "ĐANG ĐẾM NGƯỢC CHỤP ẢNH...";

        if (this.countValEl) {
            this.countValEl.textContent = count;
            this.countValEl.classList.remove("bounce");
            void this.countValEl.offsetWidth; // Trigger reflow
            this.countValEl.classList.add("bounce");
        }
    }

    /**
     * Kích hoạt hiệu ứng chớp flash máy ảnh
     */
    triggerFlash() {
        if (this.flashEl) {
            this.flashEl.classList.add("flash-active");
            setTimeout(() => this.flashEl.classList.remove("flash-active"), 450);
        }
    }

    /**
     * Chụp frame từ luồng video đang chạy và lật gương (Mirror reflection)
     * @returns {string|null} JPEG Base64 Data URL
     */
    captureFrame() {
        if (!this.videoEl || !this.videoEl.videoWidth || !this.videoEl.videoHeight) {
            if (typeof Log !== "undefined") {
                Log.warn("[CameraManager] Video stream chưa sẵn sàng để chụp frame.");
            }
            return null;
        }

        const canvas = document.createElement("canvas");
        canvas.width = this.videoEl.videoWidth;
        canvas.height = this.videoEl.videoHeight;
        const ctx = canvas.getContext("2d");

        // Lật ảnh theo trục ngang (Mirror reflection) như khi soi gương
        ctx.translate(canvas.width, 0);
        ctx.scale(-1, 1);
        ctx.drawImage(this.videoEl, 0, 0, canvas.width, canvas.height);

        return canvas.toDataURL("image/jpeg", 0.92);
    }

    /**
     * Tắt live stream và đóng camera preview
     */
    stopPreview() {
        if (this.stream) {
            try {
                this.stream.getTracks().forEach((track) => track.stop());
            } catch (e) {}
            this.stream = null;
        }
        this.isActive = false;

        if (this.videoEl) {
            this.videoEl.srcObject = null;
        }

        if (this.overlayEl) {
            this.overlayEl.style.display = "none";
            this.overlayEl.classList.remove("active");
        }

        document.body.classList.remove("camera-fullscreen-active");
    }
}

if (typeof window !== "undefined") {
    window.CameraManager = CameraManager;
}

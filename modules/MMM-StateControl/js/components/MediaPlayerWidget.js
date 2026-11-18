/**
 * ====================================================================
 *   MEDIA PLAYER WIDGET (MINI MUSIC PLAYER)
 *   Widget trình phát nhạc mini tại góc dưới bên phải (BOTTOM_RIGHT)
 *   - Đĩa than quay tít khi phát nhạc (Spinning Vinyl Disc)
 *   - Cột sóng âm thanh nhảy theo điệu nhạc (Jumping Wave Bars)
 *   - Quản lý luồng âm thanh nền HTML5 Audio API
 * ====================================================================
 */
class MediaPlayerWidget {
    constructor() {
        this.widgetEl = null;
        this.titleEl = null;
        this.artistEl = null;
        this.statusEl = null;
        this.bgAudio = null;
    }

    createDom() {
        const widget = document.createElement("div");
        widget.id = "nlu-media-player-widget";
        widget.className = "nlu-media-player-widget";
        widget.innerHTML = `
            <div class="media-icon-disc">🎵</div>
            <div class="media-info">
                <div class="media-title" id="nlu-media-title">Chưa phát nhạc</div>
                <div class="media-artist" id="nlu-media-artist">---</div>
                <div class="media-status" id="nlu-media-status">Sẵn sàng</div>
            </div>
            <div class="media-wave-bars">
                <span></span><span></span><span></span><span></span>
            </div>
        `;
        return widget;
    }

    bindDom() {
        this.widgetEl = document.getElementById("nlu-media-player-widget");
        this.titleEl = document.getElementById("nlu-media-title");
        this.artistEl = document.getElementById("nlu-media-artist");
        this.statusEl = document.getElementById("nlu-media-status");
        this._hideTimer = null;
    }

    _ensureAudio() {
        if (!this.bgAudio) {
            this.bgAudio = new Audio();
            this.bgAudio.volume = 0.75;

            const self = this;
            this.bgAudio.onended = function () {
                if (self.statusEl) self.statusEl.textContent = "Đã phát xong";
                if (self.widgetEl) self.widgetEl.classList.remove("media-playing");

                // Tự động ẩn widget sau 2.5 giây khi phát hết bài
                if (self._hideTimer) clearTimeout(self._hideTimer);
                self._hideTimer = setTimeout(() => {
                    self.hide();
                }, 2500);
            };
            this.bgAudio.onerror = function (err) {
                if (typeof Log !== "undefined") {
                    Log.warn("[MediaPlayerWidget] Audio Error hoặc không thể tải link nhạc:", err);
                }
            };
        }
        return this.bgAudio;
    }

    update(data) {
        if (!this.widgetEl) return;

        if (this.titleEl) this.titleEl.textContent = data.title || "Bài hát";
        if (this.artistEl) this.artistEl.textContent = data.artist || "Ca sĩ";

        const state = (data.state || "playing").toLowerCase();
        const audio = this._ensureAudio();
        const audioUrl = data.audio_url || data.url || "/modules/MMM-StateControl/music/sample_chill.mp3";

        if (state === "playing") {
            // Hủy timer ẩn nếu đang có
            if (this._hideTimer) {
                clearTimeout(this._hideTimer);
                this._hideTimer = null;
            }

            if (this.statusEl) this.statusEl.textContent = "Đang phát";
            this.widgetEl.classList.add("media-playing");
            this.widgetEl.classList.add("visible");

            try {
                const targetUrl = new URL(audioUrl, window.location.href).href;
                if (audio.src !== targetUrl) {
                    audio.pause();
                    audio.src = targetUrl;
                    audio.currentTime = 0;
                    audio.load();
                }
                const playPromise = audio.play();
                if (playPromise !== undefined) {
                    playPromise.then(() => {
                        if (typeof Log !== "undefined") {
                            Log.info("[MediaPlayerWidget] Đang phát nhạc: " + (data.title || ""));
                        }
                    }).catch((err) => {
                        if (typeof Log !== "undefined") {
                            Log.warn("[MediaPlayerWidget] Trình duyệt chưa cho phép phát âm thanh: ", err);
                        }
                    });
                }
            } catch (e) {
                if (typeof Log !== "undefined") {
                    Log.error("[MediaPlayerWidget] Lỗi phát nhạc:", e);
                }
            }

        } else if (state === "paused" || state === "pause" || state === "stopped" || state === "stop") {
            if (this.statusEl) this.statusEl.textContent = "Đã dừng";
            this.widgetEl.classList.remove("media-playing");
            if (this.bgAudio) {
                this.bgAudio.pause();
                if (state === "stopped" || state === "stop") {
                    this.bgAudio.currentTime = 0;
                }
            }

            // Người dùng yêu cầu tắt nhạc/dừng nhạc: Ẩn widget sau 600ms chuyển cảnh mượt mà
            if (this._hideTimer) clearTimeout(this._hideTimer);
            this._hideTimer = setTimeout(() => {
                this.hide();
            }, 600);
        }
    }

    stop() {
        if (this._hideTimer) {
            clearTimeout(this._hideTimer);
            this._hideTimer = null;
        }
        if (this.widgetEl) {
            this.widgetEl.classList.remove("media-playing");
            this.widgetEl.classList.remove("visible");
        }
        if (this.bgAudio) {
            this.bgAudio.pause();
            this.bgAudio.currentTime = 0;
        }
    }

    hide() {
        if (this._hideTimer) {
            clearTimeout(this._hideTimer);
            this._hideTimer = null;
        }
        if (this.widgetEl) {
            this.widgetEl.classList.remove("visible");
            this.widgetEl.classList.remove("media-playing");
        }
    }
}

if (typeof window !== "undefined") {
    window.MediaPlayerWidget = MediaPlayerWidget;
}

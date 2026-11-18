/**
 * ====================================================================
 *   PHOTO PREVIEW COMPONENT (PHOTO CAPTURE PREVIEW DIALOG)
 *   Khung hiển thị ảnh vừa chụp (TAKE_PHOTO / PHOTO_CAPTURED)
 *   Bao gồm: Tên tập tin ảnh, ảnh chụp sắc nét với độ rộng tối ưu,
 *   và thông báo lưu trữ vào thư mục screen_shot/.
 * ====================================================================
 */
class PhotoPreview {
    constructor() {
        this.popupEl = null;
        this.countdownBox = null;
        this.previewBox = null;
        this.previewImg = null;
        this.previewFilename = null;
    }

    createDom() {
        const popup = document.createElement("div");
        popup.id = "nlu-take-photo-popup";
        popup.className = "nlu-take-photo-popup";
        popup.innerHTML = `
            <div class="countdown-box" id="nlu-countdown-box" style="display: none;">
                <div class="countdown-circle">
                    <span class="countdown-number" id="nlu-countdown-number">3</span>
                </div>
                <div class="countdown-hint">Chuẩn bị chụp ảnh...</div>
            </div>
            <div class="photo-preview-box" id="nlu-photo-preview-box" style="display:none;">
                <div class="preview-header">
                    <span class="preview-header-badge">📸 Ảnh vừa chụp</span>
                    <span class="preview-filename" id="nlu-photo-preview-filename">photo_snapshot.jpg</span>
                </div>
                <div class="photo-preview-img-wrapper">
                    <img id="nlu-photo-preview-src" class="photo-preview-img" src="" alt="Snapshot" />
                </div>
                <div class="preview-footer">
                    <span class="preview-footer-icon">✅</span>
                    <span class="preview-footer-text">Đã lưu ảnh sắc nét vào thư mục <strong>screen_shot/</strong></span>
                </div>
            </div>
        `;
        return popup;
    }

    bindDom() {
        this.popupEl = document.getElementById("nlu-take-photo-popup");
        this.countdownBox = document.getElementById("nlu-countdown-box");
        this.previewBox = document.getElementById("nlu-photo-preview-box");
        this.previewImg = document.getElementById("nlu-photo-preview-src");
        this.previewFilename = document.getElementById("nlu-photo-preview-filename");
    }

    /**
     * Hiển thị khung ảnh vừa chụp
     * @param {string} imageUrl URL hoặc base64 data URL của ảnh
     * @param {string|null} filename Tên file đã lưu
     */
    showCaptured(imageUrl, filename = null) {
        if (!this.popupEl) return;

        if (this.countdownBox) {
            this.countdownBox.style.display = "none";
        }

        if (this.previewBox) {
            this.previewBox.style.display = "flex";
        }

        if (this.previewImg && imageUrl) {
            this.previewImg.src = imageUrl;
        }

        if (this.previewFilename) {
            if (filename) {
                this.previewFilename.textContent = filename;
            } else {
                const now = new Date();
                const pad = (n) => String(n).padStart(2, '0');
                this.previewFilename.textContent = `photo_${now.getFullYear()}${pad(now.getMonth()+1)}${pad(now.getDate())}_${pad(now.getHours())}${pad(now.getMinutes())}${pad(now.getSeconds())}.jpg`;
            }
        }

        this.popupEl.classList.add("visible");
    }

    hide() {
        if (this.popupEl) {
            this.popupEl.classList.remove("visible");
        }
    }
}

if (typeof window !== "undefined") {
    window.PhotoPreview = PhotoPreview;
}

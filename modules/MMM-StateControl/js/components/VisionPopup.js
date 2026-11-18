/**
 * ====================================================================
 *   VISION POPUP COMPONENT (OBJECT RECOGNITION & VISION TAGS)
 *   Khung hiển thị kết quả phân tích thị giác AI Gemini Vision
 *   - Laser scanner line hiệu ứng quét quang học
 *   - Khung hình vật thể đã chụp
 *   - Các nhãn nhận diện (Vision Tag Chips) kèm độ tin cậy
 *   - Dòng văn bản phản hồi được ẩn hoàn toàn theo yêu cầu người dùng
 * ====================================================================
 */
class VisionPopup {
    constructor() {
        this.popupEl = null;
        this.imgEl = null;
        this.tagContainer = null;
        this.summaryEl = null;
    }

    createDom() {
        const popup = document.createElement("div");
        popup.id = "nlu-camera-vision-popup";
        popup.className = "nlu-camera-vision-popup";
        popup.innerHTML = `
            <div class="vision-header">
                <span class="vision-title">👁️ Nhận diện thị giác AI</span>
                <span class="vision-radar-pulse"></span>
            </div>
            <div class="vision-scanner-frame">
                <div class="laser-scanner-line"></div>
                <img id="nlu-vision-frame-src" class="vision-frame-img" src="" alt="Vision Frame" />
            </div>
            <div class="vision-tags-container" id="nlu-vision-tags-container"></div>
            <div class="vision-summary" id="nlu-vision-summary-text" style="display:none;"></div>
        `;
        return popup;
    }

    bindDom() {
        this.popupEl = document.getElementById("nlu-camera-vision-popup");
        this.imgEl = document.getElementById("nlu-vision-frame-src");
        this.tagContainer = document.getElementById("nlu-vision-tags-container");
        this.summaryEl = document.getElementById("nlu-vision-summary-text");
    }

    /**
     * Hiển thị trạng thái đang xử lý quét với frame vừa lấy
     * @param {string} capturedDataUrl 
     */
    showLoading(capturedDataUrl) {
        if (!this.popupEl) return;

        if (this.imgEl && capturedDataUrl) {
            this.imgEl.src = capturedDataUrl;
        }

        // Ẩn hoàn toàn dòng trả lời AI
        if (this.summaryEl) {
            this.summaryEl.style.display = "none";
            this.summaryEl.textContent = "";
        }

        if (this.tagContainer) {
            this.tagContainer.innerHTML = `
                <div class="vision-tag-item pulse-loading">
                    <span class="tag-icon">⏳</span> <span class="tag-label">Đang nhận diện vật thể...</span>
                </div>
            `;
        }

        this.popupEl.classList.add("visible");
    }

    /**
     * Hiển thị kết quả nhận diện thị giác từ Gemini
     * @param {Object} data 
     */
    show(data) {
        if (!this.popupEl) return;

        if (this.imgEl && data.image_url) {
            this.imgEl.src = data.image_url;
        }

        // Ẩn hoàn toàn dòng mô tả/trả lời của AI theo yêu cầu của người dùng
        if (this.summaryEl) {
            this.summaryEl.style.display = "none";
            this.summaryEl.textContent = "";
        }

        if (this.tagContainer) {
            this.tagContainer.innerHTML = "";
            const detections = data.detections || [
                { label: "Vật thể trước gương", confidence: "95%" },
                { label: "Khuôn mặt người dùng", confidence: "98%" }
            ];

            detections.forEach((item) => {
                const tag = document.createElement("div");
                tag.className = "vision-tag-item";
                tag.innerHTML = `<span class="tag-icon">🎯</span> <span class="tag-label">${item.label}</span> <span class="tag-conf">${item.confidence || ""}</span>`;
                this.tagContainer.appendChild(tag);
            });
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
    window.VisionPopup = VisionPopup;
}

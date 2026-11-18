/**
 * ====================================================================
 *   KNOWLEDGE CARD COMPONENT (WEB IMAGE & ENTITY KNOWLEDGE)
 *   Thẻ thông tin tri thức & hình ảnh minh họa toàn diện (SEARCH web_image)
 *   Bao gồm: Tên thực thể, Phân loại khoa học, Tóm tắt tri thức,
 *   Key Facts Chips, và ảnh chất lượng cao kèm cơ chế tải an toàn chống vỡ hình.
 * ====================================================================
 */
class KnowledgeCard {
    constructor() {
        this.popupEl = null;
        this.imgEl = null;
        this.titleEl = null;
        this.subtitleEl = null;
        this.summaryEl = null;
        this.factsEl = null;
        this.captionEl = null;
        this.loaderEl = null;
    }

    createDom() {
        const popup = document.createElement("div");
        popup.id = "nlu-web-image-popup";
        popup.className = "nlu-web-image-popup entity-knowledge-card";
        popup.innerHTML = `
            <div class="entity-card-header">
                <div class="entity-badge">
                    <span class="entity-badge-sparkle">✦</span>
                    <span class="entity-badge-title">TRI THỨC & HÌNH ẢNH</span>
                </div>
                <h3 class="entity-title" id="nlu-web-image-title">Tìm kiếm hình ảnh</h3>
                <div class="entity-subtitle" id="nlu-entity-subtitle" style="display:none;"></div>
            </div>
            <div class="popup-image-container" id="nlu-popup-image-container">
                <div class="image-loader-spinner" id="nlu-web-image-loader">
                    <div class="spinner-ring"></div>
                    <span class="spinner-text">Đang tải hình ảnh sắc nét...</span>
                </div>
                <img id="nlu-web-image-src" class="popup-image" src="" alt="Web Image" />
            </div>
            <div class="entity-card-body">
                <div class="entity-summary" id="nlu-entity-summary" style="display:none;"></div>
                <div class="entity-facts-container" id="nlu-entity-facts" style="display:none;"></div>
            </div>
            <div class="popup-caption" id="nlu-web-image-caption"></div>
        `;
        return popup;
    }

    bindDom() {
        this.popupEl = document.getElementById("nlu-web-image-popup");
        this.imgEl = document.getElementById("nlu-web-image-src");
        this.titleEl = document.getElementById("nlu-web-image-title");
        this.subtitleEl = document.getElementById("nlu-entity-subtitle");
        this.summaryEl = document.getElementById("nlu-entity-summary");
        this.factsEl = document.getElementById("nlu-entity-facts");
        this.captionEl = document.getElementById("nlu-web-image-caption");
        this.loaderEl = document.getElementById("nlu-web-image-loader");
    }

    show(data) {
        if (!this.popupEl) return;

        // 1. Tên thực thể & phân loại
        const entityTitle = data.entity_name || data.query || "Hình ảnh";
        if (this.titleEl) this.titleEl.textContent = entityTitle;

        const subText = data.subtitle || data.scientific_name || "";
        if (this.subtitleEl) {
            this.subtitleEl.textContent = subText;
            this.subtitleEl.style.display = subText ? "block" : "none";
        }

        // 2. Tóm tắt tri thức súc tích
        const summaryText = data.summary || "";
        if (this.summaryEl) {
            this.summaryEl.textContent = summaryText;
            this.summaryEl.style.display = summaryText ? "block" : "none";
        }

        // 3. Danh sách thông số / Sự thật thú vị (Key Facts Chips)
        if (this.factsEl) {
            this.factsEl.innerHTML = "";
            const facts = Array.isArray(data.facts) ? data.facts : [];
            if (facts.length > 0) {
                facts.forEach((fact) => {
                    const chip = document.createElement("div");
                    chip.className = "entity-fact-chip";
                    chip.innerHTML = `<span class="fact-sparkle">✦</span> <span class="fact-text">${fact}</span>`;
                    this.factsEl.appendChild(chip);
                });
                this.factsEl.style.display = "flex";
            } else {
                this.factsEl.style.display = "none";
            }
        }

        // 4. Lời dẫn/chú thích ở chân thẻ
        if (this.captionEl) {
            this.captionEl.textContent = data.caption || data.response_text || "";
        }

        // 5. Quản lý tải ảnh: Xóa ảnh cũ trước để tránh hiện hình cũ
        if (this.imgEl) {
            this.imgEl.style.opacity = "0";
            if (this.loaderEl) this.loaderEl.style.display = "flex";

            const self = this;
            this.imgEl.onload = function () {
                if (self.loaderEl) self.loaderEl.style.display = "none";
                self.imgEl.style.opacity = "1";
            };

            this.imgEl.onerror = function () {
                if (self.loaderEl) self.loaderEl.style.display = "none";
                // Ảnh dự phòng thiên nhiên chất lượng cao
                self.imgEl.src = "https://images.unsplash.com/photo-1543466835-00a7907e9de1?w=1000&auto=format&fit=crop&q=80";
                self.imgEl.style.opacity = "1";
            };

            this.imgEl.src = data.image_url || "";
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
    window.KnowledgeCard = KnowledgeCard;
}

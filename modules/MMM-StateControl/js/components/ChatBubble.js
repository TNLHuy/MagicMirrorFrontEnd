/**
 * ====================================================================
 *   CHAT BUBBLE COMPONENT (CIRCULAR ORB BUBBLE)
 *   Bong bóng AI hội thoại hình cầu pha lê với hiệu ứng phản chiếu ánh sáng,
 *   sóng âm thanh mini và cơ chế gõ chữ Typewriter siêu tốc.
 * ====================================================================
 */
class ChatBubble {
    constructor(options = {}) {
        this.assistantName = options.assistantName || "Trợ lý AI";
        this.enableTypewriter = options.enableTypewriter !== false;

        this.bubbleEl = null;
        this.contentEl = null;
        this.typewriterInterval = null;
        this.cursorFadeTimer = null;
    }

    createDom() {
        const bubble = document.createElement("div");
        bubble.id = "nlu-chat-bubble";
        bubble.className = "nlu-chat-bubble circular-orb-bubble";
        bubble.innerHTML = `
            <div class="bubble-reflection-glare"></div>
            <div class="bubble-top-meta">
                <div class="bubble-badge">
                    <span class="bubble-sparkle">✦</span>
                    <span class="bubble-ai-title">${this.assistantName}</span>
                </div>
                <div class="bubble-audio-wave">
                    <span></span><span></span><span></span>
                </div>
            </div>
            <div class="bubble-content" id="nlu-chat-content"></div>
        `;
        return bubble;
    }

    bindDom() {
        this.bubbleEl = document.getElementById("nlu-chat-bubble");
        this.contentEl = document.getElementById("nlu-chat-content");
    }

    show(text) {
        if (!this.bubbleEl || !this.contentEl) return;
        this.bubbleEl.classList.add("visible");

        if (this.enableTypewriter) {
            this.renderTypewriter(text);
        } else {
            this.contentEl.textContent = text;
        }
    }

    renderTypewriter(text) {
        if (!this.contentEl) return;
        this.stopTypewriter();
        this.contentEl.innerHTML = "";

        const textSpan = document.createElement("span");
        textSpan.className = "bubble-text-content";
        const cursor = document.createElement("span");
        cursor.className = "typing-cursor";

        this.contentEl.appendChild(textSpan);
        this.contentEl.appendChild(cursor);

        let idx = 0;
        const len = text.length;
        // Tốc độ gõ siêu tốc (6-12ms) giúp câu trả lời của AI hiện ra gần như tức thì
        const speed = Math.max(6, Math.min(12, Math.round(500 / Math.max(1, len))));

        this.typewriterInterval = setInterval(() => {
            if (idx < len) {
                const step = len > 60 ? 2 : 1;
                textSpan.textContent += text.substr(idx, step);
                idx += step;
            } else {
                this.stopTypewriter();
                this.cursorFadeTimer = setTimeout(() => {
                    cursor.classList.add("fade-out");
                    setTimeout(() => {
                        if (cursor.parentNode) cursor.parentNode.removeChild(cursor);
                    }, 300);
                }, 800);
            }
        }, speed);
    }

    stopTypewriter() {
        if (this.typewriterInterval) {
            clearInterval(this.typewriterInterval);
            this.typewriterInterval = null;
        }
        if (this.cursorFadeTimer) {
            clearTimeout(this.cursorFadeTimer);
            this.cursorFadeTimer = null;
        }
    }

    hide() {
        this.stopTypewriter();
        if (this.bubbleEl) {
            this.bubbleEl.classList.remove("visible");
        }
    }
}

if (typeof window !== "undefined") {
    window.ChatBubble = ChatBubble;
}

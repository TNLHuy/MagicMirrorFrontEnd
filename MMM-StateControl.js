/**
 * Class GlowingOrb: Vẽ quả cầu năng lượng biến hình phát sáng đa sắc
 * (Phong cách Apple Intelligence / Siri iOS 18 & Google Gemini Live)
 * Chạy trực tiếp trên HTML5 Canvas 2D mượt mà 60fps, không phụ thuộc thư viện ngoài.
 */
class GlowingOrb {
    constructor(container, options = {}) {
        this.container = container;
        this.size = options.size || 280;

        this.canvas = document.createElement("canvas");
        this.canvas.className = "ai-glowing-orb-canvas";
        this.ctx = this.canvas.getContext("2d");
        this.setDimensions(this.size);
        this.container.appendChild(this.canvas);

        this.amplitude = 0.15;
        this.targetAmplitude = 0.15;
        this.speed = 0.035;
        this.targetSpeed = 0.035;
        this.subState = "listening";

        this.time = 0;
        this.running = false;
        this.animFrameId = null;

        // Các hạt bụi sao phát sáng xoay quanh quả cầu
        this.particles = [];
        for (let i = 0; i < 14; i++) {
            this.particles.push({
                angle: Math.random() * Math.PI * 2,
                orbitRadius: 0.85 + Math.random() * 0.45,
                speed: (0.008 + Math.random() * 0.018) * (Math.random() < 0.5 ? 1 : -1),
                radius: 1.2 + Math.random() * 2.2,
                alpha: 0.3 + Math.random() * 0.7
            });
        }
    }

    setDimensions(size) {
        this.size = size;
        this.width = size;
        this.height = size;
        const dpr = window.devicePixelRatio || 1;
        this.canvas.width = size * dpr;
        this.canvas.height = size * dpr;
        this.canvas.style.width = size + "px";
        this.canvas.style.height = size + "px";
        this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }

    setSubState(st) {
        this.subState = st || "listening";
        if (this.subState === "listening") {
            this.targetSpeed = 0.035;
            this.targetAmplitude = 0.15;
        } else if (this.subState === "user_speaking") {
            this.targetSpeed = 0.065;
            this.targetAmplitude = 0.55;
        } else if (this.subState === "ai_responding") {
            this.targetSpeed = 0.085;
            this.targetAmplitude = 0.80;
        }
    }

    setAmplitude(val) {
        const clamped = Math.max(0.1, Math.min(2.0, val));
        this.targetAmplitude = clamped;
    }

    start() {
        if (this.running) return;
        this.running = true;
        const loop = () => {
            if (!this.running) return;
            this.render();
            this.animFrameId = requestAnimationFrame(loop);
        };
        this.animFrameId = requestAnimationFrame(loop);
    }

    stop() {
        this.running = false;
        if (this.animFrameId) {
            cancelAnimationFrame(this.animFrameId);
            this.animFrameId = null;
        }
        if (this.ctx) {
            this.ctx.clearRect(0, 0, this.width, this.height);
        }
    }

    resize(newSize) {
        this.setDimensions(newSize);
    }

    drawSmoothBlob(ctx, pts) {
        if (pts.length < 3) return;
        ctx.beginPath();
        const last = pts[pts.length - 1];
        const first = pts[0];
        let midX = (last.x + first.x) / 2;
        let midY = (last.y + first.y) / 2;
        ctx.moveTo(midX, midY);

        for (let i = 0; i < pts.length; i++) {
            const curr = pts[i];
            const next = pts[(i + 1) % pts.length];
            midX = (curr.x + next.x) / 2;
            midY = (curr.y + next.y) / 2;
            ctx.quadraticCurveTo(curr.x, curr.y, midX, midY);
        }
        ctx.closePath();
    }

    render() {
        const ctx = this.ctx;
        const w = this.width;
        const h = this.height;
        ctx.clearRect(0, 0, w, h);

        const cx = w / 2;
        const cy = h / 2;
        const baseR = w * 0.26;

        // Nội suy mượt mà biên độ và tốc độ xoay
        this.amplitude += (this.targetAmplitude - this.amplitude) * 0.12;
        this.speed += (this.targetSpeed - this.speed) * 0.1;
        this.time += this.speed;

        // Hiệu ứng thở (breathing) khi đang chờ/lắng nghe
        let effAmp = this.amplitude;
        if (this.subState === "listening") {
            const breath = Math.sin(this.time * 1.6) * 0.08;
            effAmp = Math.max(0.12, this.amplitude + breath);
        } else if (this.subState === "user_speaking") {
            effAmp = Math.max(0.25, this.amplitude * 1.15);
        } else if (this.subState === "ai_responding") {
            const harmonic = Math.sin(this.time * 2.8) * 0.12 + Math.cos(this.time * 1.4) * 0.08;
            effAmp = Math.max(0.35, this.amplitude * 1.05 + harmonic);
        }

        const R = baseR * (1 + effAmp * 0.32);

        // 1. LỚP VẦNG HÀO QUANG TỎA SÁNG (AURA GLOW)
        const auraRadius = R * 1.75;
        const auraGrad = ctx.createRadialGradient(cx, cy, R * 0.25, cx, cy, auraRadius);
        auraGrad.addColorStop(0, "rgba(99, 102, 241, 0.50)");   // Tím Indigo
        auraGrad.addColorStop(0.35, "rgba(168, 85, 247, 0.32)"); // Tím Neon
        auraGrad.addColorStop(0.70, "rgba(236, 72, 153, 0.15)"); // Hồng Neon
        auraGrad.addColorStop(1, "rgba(0, 0, 0, 0)");
        ctx.fillStyle = auraGrad;
        ctx.beginPath();
        ctx.arc(cx, cy, auraRadius, 0, Math.PI * 2);
        ctx.fill();

        // 2. LỚP CHẤT LỎNG NỀN BIẾN HÌNH (LAYER 1 - OUTER PLASMA BLOB)
        const numPts1 = 10;
        const pts1 = [];
        for (let i = 0; i < numPts1; i++) {
            const angle = (i / numPts1) * Math.PI * 2 + this.time * 0.25;
            const w1 = Math.sin(this.time * 2.2 + i * 1.8) * 0.14 * effAmp;
            const w2 = Math.cos(this.time * 1.6 - i * 2.4) * 0.09 * effAmp;
            const r_i = R * (1 + w1 + w2);
            pts1.push({ x: cx + Math.cos(angle) * r_i, y: cy + Math.sin(angle) * r_i });
        }

        ctx.save();
        ctx.globalCompositeOperation = "lighter";
        const angleRot1 = this.time * 0.5;
        const grad1 = ctx.createLinearGradient(
            cx + Math.cos(angleRot1) * R,
            cy + Math.sin(angleRot1) * R,
            cx - Math.cos(angleRot1) * R,
            cy - Math.sin(angleRot1) * R
        );
        grad1.addColorStop(0, "#00f2fe"); // Electric Cyan
        grad1.addColorStop(0.35, "#4facfe"); // Bright Blue
        grad1.addColorStop(0.70, "#b224ef"); // Cosmic Violet
        grad1.addColorStop(1, "#ff0844"); // Neon Pink
        ctx.fillStyle = grad1;
        ctx.globalAlpha = 0.85;
        this.drawSmoothBlob(ctx, pts1);
        ctx.fill();
        ctx.restore();

        // 3. LỚP CHẤT LỎNG PHẢN CHIẾU XOAY NGƯỢC (LAYER 2 - COUNTER-ROTATING BLOB)
        const numPts2 = 8;
        const pts2 = [];
        for (let j = 0; j < numPts2; j++) {
            const angle = (j / numPts2) * Math.PI * 2 - this.time * 0.40;
            const wA = Math.sin(this.time * 3.1 - j * 2.1) * 0.16 * effAmp;
            const wB = Math.cos(this.time * 2.5 + j * 1.5) * 0.10 * effAmp;
            const r_j = (R * 0.88) * (1 + wA + wB);
            pts2.push({ x: cx + Math.cos(angle) * r_j, y: cy + Math.sin(angle) * r_j });
        }

        ctx.save();
        ctx.globalCompositeOperation = "lighter";
        const angleRot2 = -this.time * 0.7;
        const grad2 = ctx.createLinearGradient(
            cx - Math.sin(angleRot2) * R * 0.85,
            cy + Math.cos(angleRot2) * R * 0.85,
            cx + Math.sin(angleRot2) * R * 0.85,
            cy - Math.cos(angleRot2) * R * 0.85
        );
        grad2.addColorStop(0, "#ff007f"); // Hot Pink
        grad2.addColorStop(0.40, "#7928ca"); // Neon Purple
        grad2.addColorStop(0.80, "#00dfd8"); // Bright Teal
        grad2.addColorStop(1, "#0070f3"); // Azure
        ctx.fillStyle = grad2;
        ctx.globalAlpha = 0.80;
        this.drawSmoothBlob(ctx, pts2);
        ctx.fill();
        ctx.restore();

        // 4. LỚP NHÂN TRUNG TÂM PHÁT SÁNG 3D (SPECULAR GLOW CORE)
        const coreR = R * 0.58;
        const coreGrad = ctx.createRadialGradient(
            cx - R * 0.08, cy - R * 0.08, R * 0.03,
            cx, cy, coreR
        );
        coreGrad.addColorStop(0, "rgba(255, 255, 255, 0.95)");
        coreGrad.addColorStop(0.35, "rgba(220, 245, 255, 0.75)");
        coreGrad.addColorStop(0.70, "rgba(180, 100, 255, 0.35)");
        coreGrad.addColorStop(1, "rgba(0, 0, 0, 0)");
        ctx.fillStyle = coreGrad;
        ctx.beginPath();
        ctx.arc(cx, cy, coreR, 0, Math.PI * 2);
        ctx.fill();

        // 5. CÁC HẠT BỤI SAO PHÁT SÁNG BAY QUANH QUẢ CẦU (ORBITING STARDUST PARTICLES)
        ctx.save();
        for (const p of this.particles) {
            p.angle += p.speed * (1 + effAmp * 1.6);
            const pr = R * p.orbitRadius;
            const px = cx + Math.cos(p.angle) * pr;
            const py = cy + Math.sin(p.angle) * pr;
            ctx.beginPath();
            ctx.arc(px, py, p.radius, 0, Math.PI * 2);
            ctx.fillStyle = `rgba(255, 255, 255, ${p.alpha * (0.6 + effAmp * 0.4)})`;
            ctx.shadowColor = "#00f2fe";
            ctx.shadowBlur = 8;
            ctx.fill();
        }
        ctx.restore();
    }
}
//Phần trạng thái điều khiển module MagicMirror: MMM-StateControl
Module.register("MMM-StateControl", {
    defaults: {
        websocketUrl: "ws://localhost:8085",
        animationSpeed: 500
    },

    currentState: 0,
    currentSubState: "listening",
    currentText: "Tôi đang nghe bạn...",
    lockString: "STATE_CONTROL_LOCK",

    orb: null,
    stateContainerEl: null,
    textEl: null,
    currentOrbSize: 0,
    _resizeTimer: null,

    getStyles: function () {
        return ["MMM-StateControl.css"];
    },

    getScripts: function () {
        return [];
    },

    start: function () {
        Log.info("[MMM-StateControl] Starting module: " + this.name);
        this.initWebSocket();
    },

    notificationReceived: function (notification) {
        if (notification !== "DOM_OBJECTS_CREATED") return;

        const otherModules = MM.getModules().exceptModule(this);
        otherModules.enumerate((module) => {
            module.hide(0, { lockString: this.lockString });
        });
        document.body.classList.add("state-sleep");

        this.stateContainerEl = document.getElementById("state-control-container");
        this.textEl = document.getElementById("state-control-text");
        const orbHolder = document.getElementById("siri-orb-container");

        if (!this.stateContainerEl || !this.textEl || !orbHolder) {
            Log.error("[MMM-StateControl] Không tìm thấy DOM element cần thiết.");
            return;
        }

        // Đưa stateContainerEl ra trực tiếp document.body để thoát khỏi mọi transform của region cha
        if (this.stateContainerEl.parentNode !== document.body) {
            document.body.appendChild(this.stateContainerEl);
        }

        const orbSize = this.getOrbSize();
        this.currentOrbSize = orbSize;
        this.orb = new GlowingOrb(orbHolder, { size: orbSize });

        const self = this;
        window.addEventListener("resize", function () {
            clearTimeout(self._resizeTimer);
            self._resizeTimer = setTimeout(function () {
                self.resizeOrb();
            }, 300);
        });

        this.setContainerVisible(false);
    },

    initWebSocket: function () {
        const self = this;
        try {
            const socket = new WebSocket(this.config.websocketUrl);

            socket.onopen = function () {
                Log.info("[MMM-StateControl] Connected to WebSocket Server successfully!");
            };

            socket.onmessage = function (event) {
                try {
                    const data = JSON.parse(event.data);

                    if (data.type === "amplitude") {
                        self.updateAmplitude(data.value);
                        return;
                    }

                    if (typeof data.state !== "undefined") {
                        const subState = data.subState || "listening";
                        self.setSystemState(data.state, data.text || null, subState);
                    }
                } catch (e) {
                    Log.error("[MMM-StateControl] JSON Parse Error:", e);
                }
            };

            socket.onclose = function () {
                setTimeout(function () {
                    self.initWebSocket();
                }, 3000);
            };

            socket.onerror = function (error) {
                Log.error("[MMM-StateControl] WebSocket Error:", error);
            };
        } catch (err) {
            Log.error("[MMM-StateControl] WebSocket Exception:", err);
        }
    },

    setSystemState: function (newState, textPayload, subState) {
        const self = this;
        const otherModules = MM.getModules().exceptModule(this);
        const speed = this.config.animationSpeed;

        const isTopLevelChange = newState !== this.currentState;
        this.currentState = newState;

        if (newState === 0) {
            this.currentSubState = "listening";
            this.currentText = "Tôi đang nghe bạn...";
            if (isTopLevelChange) {
                otherModules.enumerate(function (module) {
                    module.hide(speed, { lockString: self.lockString });
                });
                document.body.classList.add("state-sleep");
                document.body.classList.remove("state-active");
            }
            this.setContainerVisible(false);
            if (this.orb) {
                this.orb.stop();
            }
        } else if (newState === 1) {
            this.currentSubState = "listening";
            this.currentText = "Tôi đang nghe bạn...";
            if (isTopLevelChange) {
                document.body.classList.remove("state-sleep", "state-active");
                otherModules.enumerate(function (module) {
                    module.show(speed, { lockString: self.lockString });
                });
            }
            this.setContainerVisible(false);
            if (this.orb) {
                this.orb.stop();
            }
        } else if (newState === 2) {
            this.currentSubState = subState || "listening";
            if (textPayload) this.currentText = textPayload;
            if (isTopLevelChange) {
                document.body.classList.remove("state-sleep");
                document.body.classList.add("state-active");
                otherModules.enumerate(function (module) {
                    module.hide(speed, { lockString: self.lockString });
                });
            }
            this.setContainerVisible(true);
            if (this.orb) {
                this.orb.setSubState(this.currentSubState);
                this.orb.start();
            }
        }

        if (this.textEl) this.textEl.textContent = this.currentText;

        Log.info("[MMM-StateControl] state=" + newState + " subState=" + this.currentSubState +
            " topLevelChange=" + isTopLevelChange);
    },

    setContainerVisible: function (visible) {
        if (!this.stateContainerEl) {
            Log.error("[MMM-StateControl] setContainerVisible() gọi nhưng stateContainerEl là null.");
            return;
        }
        this.stateContainerEl.classList.toggle("visible", visible);
        this.stateContainerEl.style.opacity = visible ? "1" : "0";
        this.stateContainerEl.style.pointerEvents = visible ? "auto" : "none";
    },

    updateAmplitude: function (value) {
        if (!this.orb || this.currentState !== 2) return;
        this.orb.setAmplitude(value);
    },

    getOrbSize: function () {
        const screenW = window.innerWidth || (document.documentElement && document.documentElement.clientWidth) || 1080;
        const screenH = window.innerHeight || (document.documentElement && document.documentElement.clientHeight) || 1920;
        const isPortrait = screenH > screenW;

        // Tính kích thước quả cầu cân đối theo màn hình (ngang / dọc / 4K / nhỏ)
        let size = isPortrait ? Math.round(screenW * 0.32) : Math.round(screenH * 0.28);
        size = Math.max(180, Math.min(460, size));
        return size;
    },

    resizeOrb: function () {
        if (!this.orb) return;
        const newSize = this.getOrbSize();
        if (this.currentOrbSize === newSize) return;
        this.currentOrbSize = newSize;
        this.orb.resize(newSize);
    },

    getDom: function () {
        const wrapper = document.createElement("div");
        wrapper.id = "state-control-container";
        wrapper.className = "state-container";

        const orbHolder = document.createElement("div");
        orbHolder.id = "siri-orb-container";
        orbHolder.className = "orb-holder";
        wrapper.appendChild(orbHolder);

        const text = document.createElement("div");
        text.id = "state-control-text";
        text.className = "listening-text";
        wrapper.appendChild(text);

        return wrapper;
    }
});
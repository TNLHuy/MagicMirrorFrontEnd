/**
 * ====================================================================
 *   SIRI WAVE VISUALIZER (APPLE SIRI WAVEFORM CANVAS)
 *   Uốn lượn đa sắc neon (Cyan, Purple, Blue, Pink), nhạy bén theo RMS volume.
 * ====================================================================
 */
class BottomBarSiriWave {
    constructor(container, options = {}) {
        this.container = container;
        this.width = options.width || 420;
        this.height = options.height || 64;

        this.canvas = document.createElement("canvas");
        this.canvas.className = "bottom-wave-canvas";
        this.ctx = this.canvas.getContext("2d");
        this.container.appendChild(this.canvas);

        this.amplitude = 0.08;
        this.targetAmplitude = 0.08;
        this.running = false;
        this.animId = null;
        this.phase = 0;
        this.lastTime = performance.now();

        this.resize(this.width, this.height);
    }

    resize(w, h) {
        this.width = w;
        this.height = h;
        const dpr = Math.min(window.devicePixelRatio || 1, 2);
        this.canvas.width = this.width * dpr;
        this.canvas.height = this.height * dpr;
        this.canvas.style.width = this.width + "px";
        this.canvas.style.height = this.height + "px";
        this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }

    setAmplitude(val) {
        const num = Math.max(0, Math.min(1, Number(val) || 0));
        this.targetAmplitude = Math.max(0.08, Math.min(1.0, 0.08 + num * 0.92));
    }

    start() {
        if (this.running) return;
        this.running = true;
        this.lastTime = performance.now();

        const render = (now) => {
            if (!this.running) return;
            const dt = Math.min(Math.max((now - this.lastTime) * 0.001, 0.001), 0.1);
            this.lastTime = now;

            this.amplitude += (this.targetAmplitude - this.amplitude) * 0.18;
            this.phase += dt * (2.0 + this.amplitude * 3.5) * 2.4;

            this.draw();
            this.animId = requestAnimationFrame(render);
        };
        this.animId = requestAnimationFrame(render);
    }

    stop() {
        this.running = false;
        if (this.animId) {
            cancelAnimationFrame(this.animId);
            this.animId = null;
        }
        if (this.ctx) {
            this.ctx.clearRect(0, 0, this.width, this.height);
        }
    }

    draw() {
        const ctx = this.ctx;
        const w = this.width;
        const h = this.height;
        const midY = h / 2;

        ctx.clearRect(0, 0, w, h);

        const waves = [
            { color: "rgba(0, 242, 254, 0.88)",  width: 2.6, freq: 1.8, phaseOffset: 0.0, speedMul: 1.0, glow: "#00f2fe" },
            { color: "rgba(124, 77, 255, 0.82)", width: 2.2, freq: 2.3, phaseOffset: 1.8, speedMul: 1.15, glow: "#7c4dff" },
            { color: "rgba(0, 112, 243, 0.75)",  width: 1.8, freq: 2.7, phaseOffset: 3.4, speedMul: 0.85, glow: "#0070f3" },
            { color: "rgba(255, 0, 128, 0.80)",  width: 2.0, freq: 2.0, phaseOffset: 4.9, speedMul: 1.25, glow: "#ff007f" },
            { color: "rgba(255, 255, 255, 0.95)",width: 1.4, freq: 3.2, phaseOffset: 2.4, speedMul: 1.05, glow: "#ffffff" }
        ];

        const maxWaveHeight = h * 0.45;

        waves.forEach((wv) => {
            ctx.save();
            ctx.beginPath();
            ctx.strokeStyle = wv.color;
            ctx.lineWidth = wv.width;
            ctx.lineCap = "round";
            ctx.lineJoin = "round";
            ctx.shadowColor = wv.glow;
            ctx.shadowBlur = 8 + this.amplitude * 10;

            const step = 4;
            let started = false;

            for (let x = 0; x <= w; x += step) {
                const normX = x / w;
                const envelope = Math.pow(Math.sin(normX * Math.PI), 2.0);
                const currentPhase = this.phase * wv.speedMul + wv.phaseOffset;
                const s1 = Math.sin(normX * wv.freq * Math.PI * 2 + currentPhase);
                const s2 = Math.cos(normX * (wv.freq * 1.4) * Math.PI * 2 - currentPhase * 0.5);
                const waveVal = (s1 * 0.75 + s2 * 0.25);
                const y = midY + waveVal * envelope * this.amplitude * maxWaveHeight;

                if (!started) {
                    ctx.moveTo(x, y);
                    started = true;
                } else {
                    ctx.lineTo(x, y);
                }
            }
            ctx.stroke();
            ctx.restore();
        });
    }
}

if (typeof window !== "undefined") {
    window.BottomBarSiriWave = BottomBarSiriWave;
}

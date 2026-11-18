/**
 * ====================================================================
 *   AUDIO SYNTHESIZER (WEB AUDIO API SOUND FX)
 *   Tổng hợp âm thanh trực tiếp từ trình duyệt bằng Web Audio API
 *   - Wake Chime: Âm báo thức giấc 2 âm điệu (C5 -> E5)
 *   - Countdown Beep: Tần số cao dần theo nhịp đếm (3 -> 2 -> 1)
 *   - Shutter Sound: Âm thanh cơ học màn trập máy ảnh sắc nét
 * ====================================================================
 */
class AudioSynthesizer {
    constructor(enabled = true) {
        this.enabled = enabled;
        this.audioCtx = null;
    }

    _getAudioContext() {
        if (!this.audioCtx) {
            const AudioContext = window.AudioContext || window.webkitAudioContext;
            if (AudioContext) {
                this.audioCtx = new AudioContext();
            }
        }
        if (this.audioCtx && this.audioCtx.state === "suspended") {
            this.audioCtx.resume();
        }
        return this.audioCtx;
    }

    /**
     * Âm thanh chuông báo kích hoạt trợ lý AI (Wake Chime)
     */
    playWakeChime() {
        if (!this.enabled) return;
        try {
            const ctx = this._getAudioContext();
            if (!ctx) return;

            const now = ctx.currentTime;
            
            // Nốt thứ nhất (C5 - 523.25Hz)
            const osc1 = ctx.createOscillator();
            const gain1 = ctx.createGain();
            osc1.type = "sine";
            osc1.frequency.setValueAtTime(523.25, now);
            gain1.gain.setValueAtTime(0.06, now);
            gain1.gain.exponentialRampToValueAtTime(0.0001, now + 0.30);
            osc1.connect(gain1);
            gain1.connect(ctx.destination);
            osc1.start(now);
            osc1.stop(now + 0.30);

            // Nốt thứ hai (E5 - 659.25Hz)
            const osc2 = ctx.createOscillator();
            const gain2 = ctx.createGain();
            osc2.type = "sine";
            osc2.frequency.setValueAtTime(659.25, now + 0.08);
            gain2.gain.setValueAtTime(0.08, now + 0.08);
            gain2.gain.exponentialRampToValueAtTime(0.0001, now + 0.45);
            osc2.connect(gain2);
            gain2.connect(ctx.destination);
            osc2.start(now + 0.08);
            osc2.stop(now + 0.45);
        } catch (e) {
            // Audio ignore
        }
    }

    /**
     * Âm beep đếm ngược chụp ảnh (3 -> 2 -> 1)
     * @param {number} count Số đếm hiện tại (3, 2, 1)
     */
    playCountdownBeep(count) {
        if (!this.enabled) return;
        try {
            const ctx = this._getAudioContext();
            if (!ctx) return;

            const now = ctx.currentTime;
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();

            // Tần số âm thanh đếm ngược: 3 (784Hz - G5), 2 (880Hz - A5), 1 (1046.5Hz - C6)
            const freq = count === 1 ? 1046.5 : (count === 2 ? 880.0 : 784.0);
            osc.type = "sine";
            osc.frequency.setValueAtTime(freq, now);

            gain.gain.setValueAtTime(0.08, now);
            gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.16);

            osc.connect(gain);
            gain.connect(ctx.destination);

            osc.start(now);
            osc.stop(now + 0.16);
        } catch (e) {
            // Audio ignore
        }
    }

    /**
     * Âm thanh màn trập máy ảnh (Camera Shutter)
     */
    playShutterSound() {
        try {
            const ctx = this._getAudioContext();
            if (!ctx) return;

            const now = ctx.currentTime;
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.type = "triangle";
            osc.frequency.setValueAtTime(1200, now);
            osc.frequency.exponentialRampToValueAtTime(250, now + 0.12);

            gain.gain.setValueAtTime(0.12, now);
            gain.gain.exponentialRampToValueAtTime(0.001, now + 0.12);

            osc.connect(gain);
            gain.connect(ctx.destination);

            osc.start(now);
            osc.stop(now + 0.12);
        } catch (e) {
            // Audio ignore
        }
    }
}

if (typeof window !== "undefined") {
    window.AudioSynthesizer = AudioSynthesizer;
}

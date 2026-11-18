import React, { useState } from 'react'
import { Power, Sun, Moon, Zap, Sparkles, Sliders, Palette, Activity, Check } from 'lucide-react'
import { DEFAULT_ESP32_SCENES } from '../data/mockData'

const ICON_MAP = {
  Sun,
  Moon,
  Zap,
  Sparkles,
}

const PRESET_COLORS = [
  '#f59e0b', // Warm Amber
  '#06b6d4', // Cyan Neon
  '#8b5cf6', // Deep Violet
  '#ec4899', // Magenta
  '#10b981', // Emerald
  '#f43f5e', // Ruby Rose
  '#ffffff', // Pure Daylight
]

export default function Esp32LedDeck({ isPowered, setIsPowered, onStateChange }) {
  const [activeScene, setActiveScene] = useState('cyber')
  const [brightness, setBrightness] = useState(85)
  const [color, setColor] = useState('#06b6d4')
  const [lightingMode, setLightingMode] = useState('static')
  const [lastDispatched, setLastDispatched] = useState(null)

  const handleTogglePower = () => {
    const nextPower = !isPowered
    setIsPowered(nextPower)
    dispatchChange({ power: nextPower, brightness, color, scene: activeScene, mode: lightingMode })
  }

  const handleSceneSelect = (scene) => {
    setActiveScene(scene.id)
    setColor(scene.color)
    setBrightness(scene.brightness)
    if (!isPowered) setIsPowered(true)
    dispatchChange({ power: true, brightness: scene.brightness, color: scene.color, scene: scene.id, mode: lightingMode })
  }

  const handleBrightnessChange = (e) => {
    const val = parseInt(e.target.value, 10)
    setBrightness(val)
    dispatchChange({ power: isPowered, brightness: val, color, scene: 'custom', mode: lightingMode })
  }

  const handleColorChange = (newColor) => {
    setColor(newColor)
    setActiveScene('custom')
    dispatchChange({ power: isPowered, brightness, color: newColor, scene: 'custom', mode: lightingMode })
  }

  const handleModeChange = (mode) => {
    setLightingMode(mode)
    dispatchChange({ power: isPowered, brightness, color, scene: activeScene, mode })
  }

  const dispatchChange = (payload) => {
    setLastDispatched({ ...payload, timestamp: new Date().toLocaleTimeString() })
    if (onStateChange) onStateChange(payload)
  }

  return (
    <section className="rounded-2xl border bg-white border-slate-200 shadow-sm dark:bg-[#0d1017]/90 dark:border-white/[0.08] dark:shadow-xl p-5 md:p-6 backdrop-blur-sm flex flex-col gap-5 transition-colors">
      {/* Deck Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center text-cyan-600 dark:text-cyan-400">
            <Sliders className="w-4 h-4" />
          </div>
          <div>
            <h2 className="text-base font-semibold text-slate-900 dark:text-white tracking-tight">
              Đèn LED ESP32 IoT
            </h2>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Dải LED viền gương & Chiếu sáng không gian
            </p>
          </div>
        </div>

        {/* Master Power Button */}
        <button
          onClick={handleTogglePower}
          className={`flex items-center gap-2 px-3.5 py-1.5 rounded-full text-xs font-semibold transition-all duration-200 cursor-pointer ${
            isPowered
              ? 'bg-emerald-500/20 text-emerald-700 dark:text-emerald-300 border border-emerald-500/40 shadow-[0_0_15px_rgba(16,185,129,0.25)]'
              : 'bg-slate-100 text-slate-500 border border-slate-300 dark:bg-white/[0.05] dark:text-slate-400 dark:border-white/[0.1] hover:text-slate-700 dark:hover:text-slate-200'
          }`}
        >
          <Power className={`w-3.5 h-3.5 ${isPowered ? 'text-emerald-500' : 'text-slate-400'}`} />
          <span>{isPowered ? 'ĐANG BẬT' : 'CHỜ (TẮT)'}</span>
        </button>
      </div>

      {/* Preset Scenes Grid */}
      <div className="flex flex-col gap-2">
        <span className="text-xs font-medium text-slate-600 dark:text-slate-400">Chế độ không gian</span>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
          {DEFAULT_ESP32_SCENES.map((scene) => {
            const Icon = ICON_MAP[scene.icon] || Sparkles
            const isSelected = activeScene === scene.id && isPowered

            return (
              <button
                key={scene.id}
                onClick={() => handleSceneSelect(scene)}
                className={`relative flex flex-col items-start p-3 rounded-xl border text-left transition-all duration-150 cursor-pointer ${
                  isSelected
                    ? 'border-cyan-500/50 bg-cyan-50/70 dark:bg-cyan-950/20 shadow-[0_0_12px_rgba(6,182,212,0.15)]'
                    : 'border-slate-200 bg-slate-50/60 hover:bg-slate-100 dark:border-white/[0.06] dark:bg-white/[0.02] dark:hover:bg-white/[0.04]'
                }`}
              >
                <div className="flex items-center justify-between w-full mb-1.5">
                  <div
                    className="w-6 h-6 rounded-md flex items-center justify-center text-xs"
                    style={{ backgroundColor: `${scene.color}25`, color: scene.color }}
                  >
                    <Icon className="w-3.5 h-3.5" />
                  </div>
                  {isSelected && <Check className="w-3.5 h-3.5 text-cyan-600 dark:text-cyan-400" />}
                </div>
                <span className="text-xs font-medium text-slate-800 dark:text-slate-200">{scene.name}</span>
                <span className="text-[10px] text-slate-500 dark:text-slate-400 tabular-nums">
                  {scene.brightness}% Độ sáng
                </span>
              </button>
            )
          })}
        </div>
      </div>

      {/* Brightness Slider */}
      <div className="flex flex-col gap-2">
        <div className="flex items-center justify-between text-xs">
          <span className="font-medium text-slate-600 dark:text-slate-400">Độ sáng LED</span>
          <span className="font-semibold text-slate-800 dark:text-slate-200 tabular-nums">{brightness}%</span>
        </div>
        <div className="relative flex items-center">
          <input
            type="range"
            min="0"
            max="100"
            value={brightness}
            disabled={!isPowered}
            onChange={handleBrightnessChange}
            className="w-full h-2 bg-slate-200 dark:bg-slate-800 rounded-lg appearance-none cursor-pointer accent-cyan-600 dark:accent-cyan-400 disabled:opacity-40"
          />
        </div>
      </div>

      {/* Color Palette & Custom Swatches */}
      <div className="flex flex-col gap-2">
        <div className="flex items-center justify-between text-xs">
          <span className="font-medium text-slate-600 dark:text-slate-400">Màu sắc & Tuỳ chỉnh</span>
          <span className="font-mono text-[11px] text-slate-500 dark:text-slate-400 uppercase">{color}</span>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {PRESET_COLORS.map((preset) => (
            <button
              key={preset}
              onClick={() => handleColorChange(preset)}
              disabled={!isPowered}
              className={`w-7 h-7 rounded-full border transition-all duration-150 cursor-pointer ${
                color.toLowerCase() === preset.toLowerCase()
                  ? 'scale-110 border-slate-900 dark:border-white ring-2 ring-cyan-500/50'
                  : 'border-slate-300 dark:border-white/20 hover:scale-105'
              }`}
              style={{ backgroundColor: preset }}
              title={preset}
            />
          ))}

          {/* Native HTML Color Input */}
          <label className="relative flex items-center justify-center w-7 h-7 rounded-full border border-dashed border-slate-300 dark:border-white/30 hover:border-cyan-500 cursor-pointer overflow-hidden bg-slate-100 dark:bg-slate-800">
            <Palette className="w-3.5 h-3.5 text-slate-600 dark:text-slate-300" />
            <input
              type="color"
              value={color}
              disabled={!isPowered}
              onChange={(e) => handleColorChange(e.target.value)}
              className="absolute inset-0 opacity-0 cursor-pointer w-full h-full"
            />
          </label>

          {/* Mode Pill Badges */}
          <div className="ml-auto flex items-center gap-1 bg-slate-100 dark:bg-white/[0.04] p-1 rounded-lg border border-slate-200 dark:border-white/[0.06] text-[11px]">
            {['static', 'breathe', 'wave'].map((mode) => (
              <button
                key={mode}
                onClick={() => handleModeChange(mode)}
                disabled={!isPowered}
                className={`px-2 py-0.5 rounded capitalize transition-all cursor-pointer ${
                  lightingMode === mode
                    ? 'bg-cyan-500/20 text-cyan-700 dark:text-cyan-300 border border-cyan-500/40 font-medium'
                    : 'text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200'
                }`}
              >
                {mode}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Live ESP32 Hardware Telemetry Footer */}
      <div className="pt-2 border-t border-slate-200 dark:border-white/[0.06] flex items-center justify-between text-[11px] text-slate-500 dark:text-slate-400">
        <div className="flex items-center gap-1.5">
          <Activity className="w-3.5 h-3.5 text-emerald-500 dark:text-emerald-400" />
          <span>
            Node ESP32: <strong className="text-slate-700 dark:text-slate-300 font-mono">192.168.1.120</strong>
          </span>
        </div>
        <div>
          {lastDispatched ? (
            <span className="text-cyan-600 dark:text-cyan-400 font-mono text-[10px]">
              Đã đồng bộ {lastDispatched.timestamp} ({brightness}% | {color})
            </span>
          ) : (
            <span className="text-slate-400 dark:text-slate-500">Đang lắng nghe cổng 8085</span>
          )}
        </div>
      </div>
    </section>
  )
}

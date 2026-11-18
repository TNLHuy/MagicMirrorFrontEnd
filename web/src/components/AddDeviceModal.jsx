import React, { useState } from 'react'
import {
  X,
  Lightbulb,
  Sparkles,
  Wind,
  Fan,
  Music,
  Tv,
  Cpu,
  Plus,
  Zap,
} from 'lucide-react'

const ICON_TYPES = [
  { id: 'light', name: 'Đèn chiếu sáng', icon: Lightbulb, defaultWatt: 30, color: '#f59e0b' },
  { id: 'led', name: 'Dải LED viền', icon: Sparkles, defaultWatt: 18, color: '#06b6d4' },
  { id: 'ac', name: 'Điều hòa / Làm mát', icon: Wind, defaultWatt: 850, color: '#06b6d4' },
  { id: 'fan', name: 'Quạt / Thông gió', icon: Fan, defaultWatt: 35, color: '#10b981' },
  { id: 'audio', name: 'Loa / Âm thanh', icon: Music, defaultWatt: 20, color: '#8b5cf6' },
  { id: 'tv', name: 'Tivi / Màn hình', icon: Tv, defaultWatt: 100, color: '#3b82f6' },
  { id: 'plug', name: 'Ổ cắm / Khác', icon: Cpu, defaultWatt: 50, color: '#ec4899' },
]

export default function AddDeviceModal({ isOpen, onClose, onAddDevice }) {
  const [name, setName] = useState('')
  const [location, setLocation] = useState('')
  const [selectedType, setSelectedType] = useState(ICON_TYPES[0])
  const [wattage, setWattage] = useState(30)

  if (!isOpen) return null

  const handleTypeSelect = (type) => {
    setSelectedType(type)
    setWattage(type.defaultWatt)
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    if (!name.trim()) return

    const parsedWatt = parseInt(wattage, 10) || 20
    const estKwh = parseFloat(((parsedWatt * 6) / 1000).toFixed(2)) // approx 6h daily use

    const newDevice = {
      id: `dev_${Date.now()}`,
      name: name.trim(),
      location: location.trim() || 'Nhà riêng',
      power: false,
      ratedWatt: parsedWatt,
      standbyWatt: parsedWatt > 200 ? 2 : 0.5,
      dailyKwh: estKwh,
      iconName: selectedType.id,
      color: selectedType.color,
      isCustom: true,
    }

    onAddDevice(newDevice)
    setName('')
    setLocation('')
    onClose()
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6 bg-black/60 dark:bg-black/85 backdrop-blur-md animate-in fade-in duration-150">
      <div className="relative max-w-lg w-full rounded-2xl bg-white border-slate-200 text-slate-800 dark:bg-[#0f121a] dark:border-white/10 dark:text-slate-200 border p-5 sm:p-6 shadow-2xl flex flex-col gap-4 overflow-hidden transition-colors">
        {/* Header */}
        <div className="flex items-center justify-between pb-3 border-b border-slate-200 dark:border-white/[0.08]">
          <div>
            <h3 className="text-base font-bold text-slate-900 dark:text-white">
              Thêm thiết bị IoT mới
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Cấu hình thiết bị nhà thông minh & công suất tiêu thụ
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-white/10 transition-colors cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          {/* Device Name */}
          <div className="flex flex-col gap-1">
            <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
              Tên thiết bị:
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Ví dụ: Đèn bàn làm việc, Bình nóng lạnh..."
              className="w-full text-xs px-3 py-2 rounded-xl bg-slate-50 border border-slate-300 text-slate-900 dark:bg-black/40 dark:border-white/10 dark:text-white placeholder-slate-400 outline-none focus:border-cyan-500"
              required
            />
          </div>

          {/* Location */}
          <div className="flex flex-col gap-1">
            <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
              Vị trí / Phòng:
            </label>
            <input
              type="text"
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              placeholder="Ví dụ: Phòng ngủ, Bàn học, Nhà tắm..."
              className="w-full text-xs px-3 py-2 rounded-xl bg-slate-50 border border-slate-300 text-slate-900 dark:bg-black/40 dark:border-white/10 dark:text-white placeholder-slate-400 outline-none focus:border-cyan-500"
            />
          </div>

          {/* Device Type / Icon Selector */}
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
              Loại thiết bị:
            </label>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {ICON_TYPES.map((type) => {
                const Icon = type.icon
                const isSelected = selectedType.id === type.id

                return (
                  <button
                    key={type.id}
                    type="button"
                    onClick={() => handleTypeSelect(type)}
                    className={`flex flex-col items-center gap-1 p-2 rounded-xl border text-center transition-all cursor-pointer ${
                      isSelected
                        ? 'border-cyan-500 bg-cyan-50 dark:bg-cyan-950/30 text-cyan-800 dark:text-cyan-300 shadow-sm'
                        : 'border-slate-200 bg-slate-50 dark:border-white/[0.05] dark:bg-white/[0.02] text-slate-600 dark:text-slate-400 hover:border-slate-300'
                    }`}
                  >
                    <Icon className="w-4 h-4" style={{ color: type.color }} />
                    <span className="text-[10px] font-medium leading-tight">{type.name}</span>
                  </button>
                )
              })}
            </div>
          </div>

          {/* Rated Wattage */}
          <div className="flex flex-col gap-1">
            <div className="flex items-center justify-between">
              <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 flex items-center gap-1">
                <Zap className="w-3.5 h-3.5 text-amber-500" />
                <span>Công suất khi hoạt động (Watts):</span>
              </label>
              <span className="font-bold text-xs text-slate-900 dark:text-white tabular-nums">
                {wattage} W
              </span>
            </div>
            <input
              type="number"
              min="1"
              max="5000"
              value={wattage}
              onChange={(e) => setWattage(e.target.value)}
              className="w-full text-xs font-mono px-3 py-2 rounded-xl bg-slate-50 border border-slate-300 text-slate-900 dark:bg-black/40 dark:border-white/10 dark:text-white outline-none focus:border-cyan-500"
              required
            />
            <span className="text-[10px] text-slate-400 dark:text-slate-500">
              Ước tính tiêu thụ: ~{((wattage * 6) / 1000).toFixed(2)} kWh / ngày (chạy 6 tiếng)
            </span>
          </div>

          {/* Actions */}
          <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-200 dark:border-white/[0.08]">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-xl text-xs font-medium text-slate-500 hover:text-slate-800 hover:bg-slate-100 dark:text-slate-400 dark:hover:text-white dark:hover:bg-white/[0.05] transition-colors cursor-pointer"
            >
              Hủy
            </button>
            <button
              type="submit"
              className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-cyan-600 hover:bg-cyan-500 text-white dark:bg-cyan-500 dark:hover:bg-cyan-400 dark:text-slate-950 font-semibold text-xs transition-colors shadow-md cursor-pointer"
            >
              <Plus className="w-4 h-4" />
              <span>Thêm thiết bị</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

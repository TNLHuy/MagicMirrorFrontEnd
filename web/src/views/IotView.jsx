import React, { useState, useEffect } from 'react'
import {
  Power,
  Sparkles,
  Lightbulb,
  Wind,
  Fan,
  Music,
  Tv,
  Cpu,
  Zap,
  Activity,
  Gauge,
  Plus,
  Trash2,
  PlusCircle,
  Sparkle,
} from 'lucide-react'
import AddDeviceModal from '../components/AddDeviceModal'

const ICON_MAP = {
  light: Lightbulb,
  led: Sparkles,
  ac: Wind,
  fan: Fan,
  audio: Music,
  tv: Tv,
  plug: Cpu,
}

// Sample devices preset for quick 1-click loading if user desires
const SAMPLE_PRESET_DEVICES = [
  {
    id: 'mirror_led',
    name: 'Dải LED viền gương ESP32',
    location: 'Gương thông minh (Node 192.168.1.120)',
    power: false,
    ratedWatt: 18,
    standbyWatt: 0.5,
    dailyKwh: 0.15,
    iconName: 'led',
    color: '#06b6d4',
    isMirrorLed: true,
  },
  {
    id: 'living_light',
    name: 'Đèn trần phòng khách',
    location: 'Phòng khách',
    power: false,
    ratedWatt: 40,
    standbyWatt: 0,
    dailyKwh: 0.32,
    iconName: 'light',
    color: '#f59e0b',
  },
  {
    id: 'air_conditioner',
    name: 'Máy lạnh Panasonic Inverter',
    location: 'Phòng sinh hoạt (24°C)',
    power: false,
    ratedWatt: 850,
    standbyWatt: 2,
    dailyKwh: 4.5,
    iconName: 'ac',
    color: '#06b6d4',
  },
  {
    id: 'fan',
    name: 'Quạt thông gió tự động',
    location: 'Khu vực gương',
    power: false,
    ratedWatt: 25,
    standbyWatt: 0,
    dailyKwh: 0.18,
    iconName: 'fan',
    color: '#10b981',
  },
]

export default function IotView({ isPowered, setIsPowered, onStateChange, onDeviceCountChange }) {
  // Mặc định rỗng: không có thiết bị nào được kết nối sẵn
  const [devices, setDevices] = useState(() => {
    try {
      const saved = localStorage.getItem('magicmirror_iot_devices')
      if (saved !== null) {
        const parsed = JSON.parse(saved)
        if (Array.isArray(parsed)) return parsed
      }
    } catch {
      // Fallback
    }
    return [] // Mặc định không có thiết bị nào
  })

  const [isAddModalOpen, setIsAddModalOpen] = useState(false)

  // Save devices on state changes and notify parent
  useEffect(() => {
    localStorage.setItem('magicmirror_iot_devices', JSON.stringify(devices))
    if (onDeviceCountChange) {
      onDeviceCountChange(devices.length)
    }
  }, [devices, onDeviceCountChange])

  // Sync ESP32 LED state with parent isPowered if a mirror LED exists
  useEffect(() => {
    setDevices((prev) =>
      prev.map((d) => (d.isMirrorLed ? { ...d, power: isPowered } : d))
    )
  }, [isPowered])

  const handleToggleDevice = (id) => {
    setDevices((prev) =>
      prev.map((dev) => {
        if (dev.id === id) {
          const nextPower = !dev.power
          if (dev.isMirrorLed) {
            setIsPowered(nextPower)
            if (onStateChange) {
              onStateChange({
                power: nextPower,
                timestamp: new Date().toLocaleTimeString(),
              })
            }
          }
          return { ...dev, power: nextPower }
        }
        return dev
      })
    )
  }

  const handleAddDevice = (newDevice) => {
    setDevices((prev) => [...prev, newDevice])
  }

  // Bất kỳ thiết bị nào thêm vào cũng xóa được
  const handleDeleteDevice = (id) => {
    setDevices((prev) => prev.filter((d) => d.id !== id))
  }

  const handleLoadSampleDevices = () => {
    setDevices(SAMPLE_PRESET_DEVICES)
  }

  const handleClearAllDevices = () => {
    setDevices([])
  }

  // Calculate live instant power and estimated daily energy
  const activeCount = devices.filter((d) => d.power).length
  const currentTotalWatt = devices.reduce(
    (sum, d) => sum + (d.power ? d.ratedWatt : d.standbyWatt),
    0
  )
  const currentTotalKwh = devices
    .reduce((sum, d) => sum + (d.power ? d.dailyKwh : 0), 0)
    .toFixed(2)

  return (
    <div className="flex flex-col gap-6 max-w-5xl w-full mx-auto">
      {/* View Header with Live Telemetry */}
      <div className="flex flex-wrap items-center justify-between gap-4 pb-3 border-b border-slate-200 dark:border-white/[0.08]">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-xl font-bold text-slate-900 dark:text-white tracking-tight">
              Thiết bị IoT & Điện năng tiêu thụ
            </h2>
            <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-cyan-500/15 text-cyan-700 dark:text-cyan-300 border border-cyan-500/30">
              {devices.length} Thiết bị
            </span>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Tự do thêm thiết bị, bật/tắt nguồn và xóa thiết bị bất kỳ lúc nào
          </p>
        </div>

        {/* Actions & Real-time Energy Badges */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Add Device Button */}
          <button
            onClick={() => setIsAddModalOpen(true)}
            className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-cyan-600 hover:bg-cyan-500 text-white dark:bg-cyan-500 dark:hover:bg-cyan-400 dark:text-slate-950 text-xs font-semibold shadow-md cursor-pointer transition-all"
          >
            <Plus className="w-4 h-4" />
            <span>Thêm thiết bị mới</span>
          </button>

          {/* Wattage Badge */}
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl border border-amber-200 bg-amber-50 dark:border-amber-500/30 dark:bg-amber-950/20 text-xs shadow-sm">
            <Zap className="w-3.5 h-3.5 text-amber-600 dark:text-amber-400" />
            <span className="text-amber-800 dark:text-amber-300 font-medium">Công suất:</span>
            <span className="font-bold text-amber-950 dark:text-amber-200 tabular-nums">
              {currentTotalWatt} W
            </span>
          </div>

          {/* Daily Energy Badge */}
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl border border-emerald-200 bg-emerald-50 dark:border-emerald-500/30 dark:bg-emerald-950/20 text-xs shadow-sm">
            <Gauge className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
            <span className="text-emerald-800 dark:text-emerald-300 font-medium">Hôm nay:</span>
            <span className="font-bold text-emerald-950 dark:text-emerald-200 tabular-nums">
              {currentTotalKwh} kWh
            </span>
          </div>
        </div>
      </div>

      {/* When no devices connected */}
      {devices.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 px-6 rounded-2xl border border-dashed border-slate-300 dark:border-white/10 bg-white/50 dark:bg-[#0d1017]/40 text-center">
          <div className="w-14 h-14 rounded-2xl bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center text-cyan-600 dark:text-cyan-400 mb-3 shadow-sm">
            <Cpu className="w-7 h-7" />
          </div>
          <h3 className="text-base font-bold text-slate-800 dark:text-slate-100">
            Chưa có thiết bị IoT nào được kết nối
          </h3>
          <p className="text-xs text-slate-500 dark:text-slate-400 max-w-md mt-1 leading-relaxed">
            Mặc định hệ thống để trống để bạn tự do thêm các thiết bị thực tế trong nhà (dải đèn LED viền gương, bóng đèn, quạt, điều hòa...).
          </p>

          <div className="flex flex-wrap items-center gap-3 mt-5">
            <button
              onClick={() => setIsAddModalOpen(true)}
              className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-cyan-600 hover:bg-cyan-500 text-white dark:bg-cyan-500 dark:hover:bg-cyan-400 dark:text-slate-950 text-xs font-semibold shadow-md cursor-pointer transition-all"
            >
              <Plus className="w-4 h-4" />
              <span>Thêm thiết bị đầu tiên</span>
            </button>

            <button
              onClick={handleLoadSampleDevices}
              className="flex items-center gap-1.5 px-4 py-2 rounded-xl border border-slate-300 bg-white hover:bg-slate-50 text-slate-700 dark:border-white/10 dark:bg-white/[0.04] dark:hover:bg-white/[0.08] dark:text-slate-200 text-xs font-medium cursor-pointer transition-all"
            >
              <Sparkle className="w-3.5 h-3.5 text-cyan-500" />
              <span>Nạp 4 thiết bị mẫu nhanh</span>
            </button>
          </div>
        </div>
      ) : (
        /* Grid of Device Cards */
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {devices.map((device) => {
            const Icon = ICON_MAP[device.iconName] || Cpu
            const currentWatt = device.power ? device.ratedWatt : device.standbyWatt

            return (
              <div
                key={device.id}
                className={`group relative rounded-2xl border p-5 flex flex-col justify-between gap-4 transition-all duration-200 ${
                  device.power
                    ? 'bg-white border-slate-300 shadow-sm dark:bg-[#0d1017]/95 dark:border-white/[0.12] dark:shadow-[0_0_15px_rgba(6,182,212,0.08)]'
                    : 'bg-slate-50/70 border-slate-200 dark:bg-white/[0.02] dark:border-white/[0.05] opacity-80'
                }`}
              >
                {/* Card Header: Icon & Controls */}
                <div className="flex items-start justify-between">
                  <div
                    className="w-10 h-10 rounded-xl flex items-center justify-center transition-colors"
                    style={{
                      backgroundColor: device.power ? `${device.color}20` : 'rgba(148, 163, 184, 0.15)',
                      color: device.power ? device.color : '#94a3b8',
                    }}
                  >
                    <Icon className="w-5 h-5" />
                  </div>

                  <div className="flex items-center gap-1.5">
                    {/* Bất kỳ thiết bị nào cũng xóa được */}
                    <button
                      onClick={() => handleDeleteDevice(device.id)}
                      className="p-1.5 rounded-lg text-slate-400 hover:text-rose-500 hover:bg-rose-50 dark:hover:bg-rose-500/10 transition-colors cursor-pointer"
                      title="Xóa thiết bị này khỏi danh sách"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>

                    {/* On / Off Switch Button */}
                    <button
                      onClick={() => handleToggleDevice(device.id)}
                      className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold transition-all duration-200 cursor-pointer ${
                        device.power
                          ? 'bg-emerald-500/20 text-emerald-700 dark:text-emerald-300 border border-emerald-500/40 shadow-sm'
                          : 'bg-slate-200 text-slate-600 border border-slate-300 dark:bg-white/[0.06] dark:text-slate-400 dark:border-white/10 hover:text-slate-800 dark:hover:text-slate-200'
                      }`}
                      title={device.power ? 'Bấm để tắt thiết bị' : 'Bấm để bật thiết bị'}
                    >
                      <Power
                        className={`w-3.5 h-3.5 ${
                          device.power ? 'text-emerald-600 dark:text-emerald-400' : 'text-slate-400'
                        }`}
                      />
                      <span>{device.power ? 'BẬT' : 'TẮT'}</span>
                    </button>
                  </div>
                </div>

                {/* Card Body: Names & Location */}
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="text-sm font-bold text-slate-900 dark:text-white leading-tight">
                      {device.name}
                    </h3>
                    {device.isMirrorLed && (
                      <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-cyan-500/15 text-cyan-700 dark:text-cyan-300 border border-cyan-500/30">
                        ESP32
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                    {device.location}
                  </p>
                </div>

                {/* Card Footer: Power Consumption Telemetry */}
                <div className="pt-3 border-t border-slate-200/80 dark:border-white/[0.06] flex items-center justify-between text-xs">
                  <div className="flex flex-col">
                    <span className="text-[11px] text-slate-400 dark:text-slate-500 font-medium">
                      Công suất:
                    </span>
                    <div className="flex items-center gap-1 mt-0.5">
                      <Zap
                        className={`w-3.5 h-3.5 ${
                          device.power
                            ? 'text-amber-500 dark:text-amber-400'
                            : 'text-slate-400 dark:text-slate-600'
                        }`}
                      />
                      <span
                        className={`font-bold tabular-nums text-sm ${
                          device.power
                            ? 'text-slate-900 dark:text-slate-100'
                            : 'text-slate-400 dark:text-slate-500'
                        }`}
                      >
                        {currentWatt} W
                      </span>
                      <span className="text-[10px] text-slate-400 dark:text-slate-500">
                        {device.power ? '(Đang chạy)' : '(Chờ)'}
                      </span>
                    </div>
                  </div>

                  <div className="flex flex-col items-end">
                    <span className="text-[11px] text-slate-400 dark:text-slate-500 font-medium">
                      Ước tính ngày:
                    </span>
                    <span className="font-semibold text-slate-700 dark:text-slate-300 tabular-nums mt-0.5">
                      {device.power ? `${device.dailyKwh} kWh` : '0 kWh'}
                    </span>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* Footer controls when devices exist */}
      {devices.length > 0 && (
        <div className="flex items-center justify-between pt-1 text-xs text-slate-400">
          <span className="text-[11px]">
            Đang hiển thị {devices.length} thiết bị ({activeCount} thiết bị đang hoạt động)
          </span>
          <button
            onClick={handleClearAllDevices}
            className="text-[11px] text-rose-500 hover:underline cursor-pointer"
          >
            Xóa toàn bộ thiết bị
          </button>
        </div>
      )}

      {/* Add Device Modal */}
      <AddDeviceModal
        isOpen={isAddModalOpen}
        onClose={() => setIsAddModalOpen(false)}
        onAddDevice={handleAddDevice}
      />
    </div>
  )
}

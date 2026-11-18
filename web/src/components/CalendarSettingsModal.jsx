import React, { useState } from 'react'
import {
  X,
  Calendar,
  Link2,
  Server,
  Save,
  Check,
  HelpCircle,
  Plus,
  Trash2,
  RefreshCw,
  Eye,
  EyeOff,
} from 'lucide-react'

const COLOR_PRESETS = [
  '#06b6d4', // Cyan
  '#10b981', // Emerald
  '#8b5cf6', // Violet
  '#f59e0b', // Amber
  '#f43f5e', // Rose
  '#3b82f6', // Blue
]

export default function CalendarSettingsModal({
  isOpen,
  onClose,
  calendars,
  piIp,
  onSave,
}) {
  const [calendarList, setCalendarList] = useState(() => {
    return calendars && calendars.length > 0
      ? JSON.parse(JSON.stringify(calendars))
      : [
          {
            id: 'cal_vietnam_holidays',
            name: 'Ngày lễ Việt Nam',
            url: 'https://calendar.google.com/calendar/ical/vi.vietnamese%23holiday%40group.v.calendar.google.com/public/basic.ics',
            color: '#10b981',
            enabled: true,
          },
        ]
  })

  const [hostIp, setHostIp] = useState(piIp || '192.168.1.100:8080')
  const [syncToPi, setSyncToPi] = useState(true)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [showHelp, setShowHelp] = useState(false)
  const [successToast, setSuccessToast] = useState(false)

  if (!isOpen) return null

  const handleAddCalendar = () => {
    const nextColor = COLOR_PRESETS[calendarList.length % COLOR_PRESETS.length]
    const newCal = {
      id: `cal_${Date.now()}`,
      name: `Lịch mới ${calendarList.length + 1}`,
      url: '',
      color: nextColor,
      enabled: true,
    }
    setCalendarList([...calendarList, newCal])
  }

  const handleUpdateCalendar = (index, field, value) => {
    const updated = [...calendarList]
    updated[index] = { ...updated[index], [field]: value }
    setCalendarList(updated)
  }

  const handleDeleteCalendar = (index) => {
    const updated = calendarList.filter((_, i) => i !== index)
    setCalendarList(updated)
  }

  const handleAddVietnamHolidays = () => {
    const exists = calendarList.some((c) => c.url.includes('vi.vietnamese#holiday'))
    if (!exists) {
      setCalendarList([
        ...calendarList,
        {
          id: 'cal_vietnam_holidays',
          name: 'Ngày lễ Việt Nam',
          url: 'https://calendar.google.com/calendar/ical/vi.vietnamese%23holiday%40group.v.calendar.google.com/public/basic.ics',
          color: '#10b981',
          enabled: true,
        },
      ])
    }
  }

  const handleSave = async (e) => {
    e.preventDefault()
    setIsSubmitting(true)

    // Save to localStorage
    localStorage.setItem('magicmirror_calendars', JSON.stringify(calendarList))
    localStorage.setItem('magicmirror_pi_ip', hostIp.trim())

    // 1. Luôn gửi trực tiếp về API của MagicMirror Server (/api/calendars)
    try {
      await fetch('/api/calendars', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(calendarList),
      })
    } catch (err) {
      console.warn('Lỗi lưu lịch về API:', err)
    }

    // 2. Nếu người dùng nhập host IP riêng và bật đồng bộ mạng ngoài
    if (syncToPi && hostIp && typeof window !== 'undefined' && hostIp !== window.location.host) {
      try {
        await fetch(`http://${hostIp.replace(/^https?:\/\//, '')}/api/calendar/sync`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(calendarList),
          mode: 'no-cors',
        })
      } catch (err) {
        console.info('Raspberry Pi sync dispatched (remote network).', err)
      }
    }

    setIsSubmitting(false)
    setSuccessToast(true)

    setTimeout(() => {
      onSave({ calendars: calendarList, piIp: hostIp.trim(), syncToPi })
      onClose()
    }, 500)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6 bg-black/60 dark:bg-black/85 backdrop-blur-md animate-in fade-in duration-150">
      <div className="relative max-w-2xl w-full max-h-[90vh] rounded-2xl bg-white border-slate-200 text-slate-800 dark:bg-[#0f121a] dark:border-white/10 dark:text-slate-200 border p-5 sm:p-6 shadow-2xl flex flex-col gap-4 overflow-hidden transition-colors">
        {/* Header */}
        <div className="flex items-center justify-between pb-3 border-b border-slate-200 dark:border-white/[0.08]">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-600 dark:text-emerald-400">
              <Calendar className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-base font-semibold text-slate-900 dark:text-white">
                Quản lý Lịch Google (iCal Multi-feed)
              </h3>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Thêm nhiều link lịch và chọn lịch cần hiển thị
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-white/10 transition-colors cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Scrollable Form Body */}
        <form onSubmit={handleSave} className="flex flex-col gap-4 overflow-y-auto pr-1">
          {/* Calendar Feeds List */}
          <div className="flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-slate-700 dark:text-slate-200">
                Danh sách nguồn lịch ({calendarList.length})
              </span>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={handleAddVietnamHolidays}
                  className="text-[11px] text-emerald-600 dark:text-emerald-400 hover:underline cursor-pointer"
                >
                  + Ngày lễ VN
                </button>
                <button
                  type="button"
                  onClick={() => setShowHelp(!showHelp)}
                  className="text-[11px] text-cyan-600 dark:text-cyan-400 hover:underline flex items-center gap-1 cursor-pointer"
                >
                  <HelpCircle className="w-3 h-3" />
                  <span>Cách lấy link .ics?</span>
                </button>
              </div>
            </div>

            {/* Help box */}
            {showHelp && (
              <div className="p-3.5 rounded-xl bg-cyan-50 border-cyan-200 text-slate-700 dark:bg-cyan-950/30 dark:border-cyan-500/20 dark:text-slate-300 border text-xs flex flex-col gap-1.5 leading-relaxed animate-in fade-in">
                <span className="font-semibold text-cyan-700 dark:text-cyan-300">
                  Cách lấy link iCal bí mật từ Google Calendar:
                </span>
                <ol className="list-decimal list-inside space-y-1 text-slate-600 dark:text-slate-400 text-[11px]">
                  <li>Mở Google Calendar trên máy tính (calendar.google.com).</li>
                  <li>Bấm vào dấu 3 chấm cạnh tên lịch ở cột trái → <strong>Cài đặt và chia sẻ</strong>.</li>
                  <li>Kéo xuống mục <strong>Tích hợp lịch</strong>.</li>
                  <li>Sao chép link trong ô <strong>Địa chỉ bí mật ở định dạng iCal</strong> (.ics).</li>
                  <li>Dán vào ô URL bên dưới rồi bấm Lưu & Đồng bộ.</li>
                </ol>
              </div>
            )}

            {/* Feeds Card List */}
            <div className="flex flex-col gap-2.5">
              {calendarList.map((cal, idx) => (
                <div
                  key={cal.id || idx}
                  className={`p-3 rounded-xl border transition-all ${
                    cal.enabled
                      ? 'border-slate-200 bg-slate-50/70 dark:border-white/[0.1] dark:bg-white/[0.02]'
                      : 'border-slate-100 bg-slate-50/30 dark:border-white/[0.04] dark:bg-white/[0.01] opacity-60'
                  }`}
                >
                  <div className="flex items-center gap-2.5 mb-2">
                    {/* Toggle show/hide */}
                    <button
                      type="button"
                      onClick={() => handleUpdateCalendar(idx, 'enabled', !cal.enabled)}
                      className={`p-1 rounded-md transition-colors cursor-pointer ${
                        cal.enabled
                          ? 'text-cyan-600 bg-cyan-100/60 dark:text-cyan-400 dark:bg-cyan-500/10'
                          : 'text-slate-400 bg-slate-200/50 dark:text-slate-500 dark:bg-white/[0.05]'
                      }`}
                      title={cal.enabled ? 'Đang hiển thị (Bấm để ẩn)' : 'Đang ẩn (Bấm để hiển thị)'}
                    >
                      {cal.enabled ? <Eye className="w-4 h-4" /> : <EyeOff className="w-4 h-4" />}
                    </button>

                    {/* Color Swatch Picker */}
                    <div className="flex items-center gap-1">
                      {COLOR_PRESETS.map((color) => (
                        <button
                          key={color}
                          type="button"
                          onClick={() => handleUpdateCalendar(idx, 'color', color)}
                          className={`w-4 h-4 rounded-full border transition-all cursor-pointer ${
                            cal.color === color
                              ? 'scale-125 border-slate-800 dark:border-white ring-1 ring-slate-400 dark:ring-white/50'
                              : 'border-transparent hover:scale-110 opacity-70 hover:opacity-100'
                          }`}
                          style={{ backgroundColor: color }}
                        />
                      ))}
                    </div>

                    {/* Calendar Name */}
                    <input
                      type="text"
                      value={cal.name}
                      onChange={(e) => handleUpdateCalendar(idx, 'name', e.target.value)}
                      placeholder="Tên lịch (vd: Cá nhân, Công việc)"
                      className="flex-1 text-xs font-semibold px-2.5 py-1 rounded-lg bg-white border border-slate-300 text-slate-800 dark:bg-black/40 dark:border-white/10 dark:text-white placeholder-slate-400 outline-none focus:border-cyan-500"
                      required
                    />

                    {/* Delete button */}
                    {calendarList.length > 1 && (
                      <button
                        type="button"
                        onClick={() => handleDeleteCalendar(idx)}
                        className="p-1 rounded-md text-slate-400 hover:text-rose-600 hover:bg-rose-50 dark:text-slate-500 dark:hover:text-rose-400 dark:hover:bg-rose-500/10 transition-colors cursor-pointer"
                        title="Xóa lịch này"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>

                  {/* URL Input */}
                  <div className="flex items-center gap-2">
                    <Link2 className="w-3.5 h-3.5 text-slate-400 dark:text-slate-500 shrink-0" />
                    <input
                      type="text"
                      value={cal.url}
                      onChange={(e) => handleUpdateCalendar(idx, 'url', e.target.value)}
                      placeholder="https://calendar.google.com/calendar/ical/.../basic.ics"
                      className="w-full text-[11px] font-mono px-2 py-1 rounded-lg bg-white border border-slate-300 text-slate-700 dark:bg-black/40 dark:border-white/10 dark:text-slate-300 placeholder-slate-400 outline-none focus:border-cyan-500"
                    />
                  </div>
                </div>
              ))}
            </div>

            {/* Add Calendar Button */}
            <button
              type="button"
              onClick={handleAddCalendar}
              className="flex items-center justify-center gap-1.5 py-2 px-3 rounded-xl border border-dashed border-slate-300 hover:border-cyan-500 hover:bg-cyan-50 text-slate-700 dark:border-white/20 dark:hover:border-cyan-400/50 dark:hover:bg-cyan-500/5 dark:text-slate-300 text-xs font-medium transition-all cursor-pointer"
            >
              <Plus className="w-3.5 h-3.5 text-cyan-600 dark:text-cyan-400" />
              <span>Thêm nguồn lịch mới (+ Add Calendar)</span>
            </button>
          </div>

          {/* Raspberry Pi Sync Section */}
          <div className="p-3.5 rounded-xl bg-slate-50 border-slate-200 dark:bg-white/[0.02] dark:border-white/[0.06] border flex flex-col gap-2">
            <div className="flex items-center justify-between">
              <label className="text-xs font-medium text-slate-700 dark:text-slate-300 flex items-center gap-1.5">
                <Server className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
                <span>Đồng bộ sang Smart Mirror (Raspberry Pi)</span>
              </label>
              <input
                type="checkbox"
                id="syncToPi"
                checked={syncToPi}
                onChange={(e) => setSyncToPi(e.target.checked)}
                className="w-4 h-4 rounded border-slate-300 text-cyan-600 focus:ring-cyan-500 dark:border-slate-700 dark:bg-slate-900 dark:text-cyan-500 cursor-pointer"
              />
            </div>

            <div className="flex items-center gap-2">
              <span className="text-[11px] text-slate-500 dark:text-slate-400 whitespace-nowrap">IP Gương:</span>
              <input
                type="text"
                value={hostIp}
                onChange={(e) => setHostIp(e.target.value)}
                placeholder="192.168.1.100:8080"
                className="flex-1 text-xs font-mono p-1.5 px-2.5 rounded-lg bg-white border border-slate-300 text-slate-800 dark:bg-black/40 dark:border-white/10 dark:text-white placeholder-slate-400 outline-none"
              />
            </div>
            <p className="text-[11px] text-slate-500 leading-snug">
              Cập nhật đồng thời tất cả các lịch đã bật vào module calendar ở góc dưới bên trái của gương thật.
            </p>
          </div>

          {/* Actions */}
          <div className="flex items-center justify-end gap-2.5 pt-2 border-t border-slate-200 dark:border-white/[0.08]">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-xl text-xs font-medium text-slate-500 hover:text-slate-800 hover:bg-slate-100 dark:text-slate-400 dark:hover:text-white dark:hover:bg-white/[0.05] transition-colors cursor-pointer"
            >
              Hủy
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-cyan-600 hover:bg-cyan-500 text-white dark:bg-cyan-500 dark:hover:bg-cyan-400 dark:text-slate-950 font-semibold text-xs transition-colors shadow-md disabled:opacity-50 cursor-pointer"
            >
              {successToast ? (
                <>
                  <Check className="w-4 h-4 text-white dark:text-slate-950" />
                  <span>Đã lưu!</span>
                </>
              ) : isSubmitting ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin text-white dark:text-slate-950" />
                  <span>Đang đồng bộ...</span>
                </>
              ) : (
                <>
                  <Save className="w-4 h-4" />
                  <span>Lưu & Đồng bộ</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

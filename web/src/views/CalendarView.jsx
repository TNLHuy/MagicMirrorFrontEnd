import React, { useState, useEffect, useMemo, useRef } from 'react'
import {
  Calendar as CalendarIcon,
  Settings,
  RefreshCw,
  MapPin,
  CheckCircle2,
  Filter,
  Plus,
  Eye,
  EyeOff,
  Server,
} from 'lucide-react'
import CalendarSettingsModal from '../components/CalendarSettingsModal'
import { formatEventTiming } from '../utils/icsParser'
import { DEFAULT_CALENDARS } from '../data/mockData'

export default function CalendarView() {
  const [calendars, setCalendars] = useState(() => {
    try {
      const saved = localStorage.getItem('magicmirror_calendars')
      if (saved) {
        const parsed = JSON.parse(saved)
        if (Array.isArray(parsed) && parsed.length > 0) return parsed
      }
    } catch {
      // Fallback
    }
    return DEFAULT_CALENDARS
  })

  const [piIp, setPiIp] = useState(() => {
    return localStorage.getItem('magicmirror_pi_ip') || '192.168.1.100:8080'
  })

  const [selectedCalendarIds, setSelectedCalendarIds] = useState(() => {
    return new Set(calendars.filter((c) => c.enabled !== false).map((c) => c.id))
  })

  const [rawEventsByCal, setRawEventsByCal] = useState({})
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [lastSyncTime, setLastSyncTime] = useState(null)
  const [calendarErrors, setCalendarErrors] = useState([])
  const [displayDays, setDisplayDays] = useState(7)
  const eventListRef = useRef(null)

  // Đồng bộ danh sách lịch từ máy chủ Raspberry Pi / MagicMirror (/api/calendars)
  useEffect(() => {
    const fetchBackendCalendars = async () => {
      try {
        const res = await fetch('/api/calendars')
        if (res.ok) {
          const data = await res.json()
          if (Array.isArray(data) && data.length > 0) {
            setCalendars(data)
            localStorage.setItem('magicmirror_calendars', JSON.stringify(data))
          }
        }
      } catch (err) {
        console.warn('Cannot fetch /api/calendars, using local state:', err)
      }
    }
    fetchBackendCalendars()
  }, [])

  useEffect(() => {
    setSelectedCalendarIds(
      new Set(calendars.filter((c) => c.enabled !== false).map((c) => c.id))
    )
  }, [calendars])

  const fetchAllCalendars = async (calsToFetch = calendars) => {
    setIsLoading(true)
    const newEventsMap = {}
    const errors = []
    const from = new Date()
    from.setHours(0, 0, 0, 0)
    const to = new Date(from)
    // Keep a 30-day window so switching ranges is immediate.
    to.setDate(to.getDate() + 30)
    to.setMilliseconds(-1)

    for (const cal of calsToFetch) {
      if (!cal.url || !cal.url.trim()) {
        newEventsMap[cal.id] = []
        continue
      }

      try {
        let text = null
        // Tải qua máy chủ trước để tránh CORS của Google Calendar.
        try {
          // /cors đọc URL nguyên bản, gồm cả các ký tự % đã mã hóa.
          const proxyRes = await fetch(`/cors?url=${cal.url.trim()}`, {
            signal: AbortSignal.timeout(15000),
          })
          if (!proxyRes.ok) {
            throw new Error(proxyRes.status === 403
              ? 'Máy chủ chưa cho phép tải nguồn lịch này. Kiểm tra cấu hình CORS và khởi động lại máy chủ.'
              : `Không tải được lịch qua máy chủ (HTTP ${proxyRes.status}).`)
          }
          text = await proxyRes.text()
        } catch (proxyError) {
          try {
            const directRes = await fetch(cal.url.trim(), {
              signal: AbortSignal.timeout(15000),
            })
            if (!directRes.ok) {
              throw new Error(`HTTP ${directRes.status}`)
            }
            text = await directRes.text()
          } catch {
            throw proxyError
          }
        }

        if (!text || !text.includes('BEGIN:VCALENDAR')) {
          throw new Error('Nguồn lịch không trả về dữ liệu ICS. Kiểm tra quyền chia sẻ hoặc địa chỉ iCal.')
        }
        const occurrencesRes = await fetch('/api/calendar/occurrences', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ ics: text, from: from.toISOString(), to: to.toISOString() }),
          signal: AbortSignal.timeout(15000),
        })
        if (!occurrencesRes.ok) {
          throw new Error('Không tính được các buổi học sắp tới. Hãy thử làm mới lịch.')
        }
        newEventsMap[cal.id] = (await occurrencesRes.json()).map((event) => ({
          ...event,
          calendarId: cal.id,
          calendarName: cal.name,
          color: cal.color,
        }))
      } catch (error) {
        newEventsMap[cal.id] = []
        errors.push(`${cal.name}: ${error.message || 'Không thể kết nối nguồn lịch.'}`)
      }
    }

    setRawEventsByCal(newEventsMap)
    setCalendarErrors(errors)
    if (errors.length === 0) {
      setLastSyncTime(new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }))
    }
    setIsLoading(false)
  }

  useEffect(() => {
    fetchAllCalendars(calendars)
    const timer = setInterval(() => fetchAllCalendars(calendars), 60000)
    return () => clearInterval(timer)
  }, [calendars])

  const handleToggleFilter = (calId) => {
    const nextSet = new Set(selectedCalendarIds)
    if (nextSet.has(calId)) {
      if (nextSet.size > 1) {
        nextSet.delete(calId)
      }
    } else {
      nextSet.add(calId)
    }
    setSelectedCalendarIds(nextSet)

    const updated = calendars.map((c) => ({
      ...c,
      enabled: nextSet.has(c.id),
    }))
    setCalendars(updated)
    localStorage.setItem('magicmirror_calendars', JSON.stringify(updated))
  }

  const handleSelectAll = () => {
    const allIds = new Set(calendars.map((c) => c.id))
    setSelectedCalendarIds(allIds)
    const updated = calendars.map((c) => ({ ...c, enabled: true }))
    setCalendars(updated)
    localStorage.setItem('magicmirror_calendars', JSON.stringify(updated))
  }

  const visibleEvents = useMemo(() => {
    const combined = []
    const from = new Date()
    from.setHours(0, 0, 0, 0)
    const until = new Date(from)
    until.setDate(until.getDate() + displayDays)

    for (const calId of selectedCalendarIds) {
      const evts = rawEventsByCal[calId] || []
      combined.push(...evts.filter((event) => {
        const start = new Date(event.start)
        return start >= from && start < until
      }))
    }

    return combined.sort(
      (a, b) => (new Date(a.start).getTime() || 0) - (new Date(b.start).getTime() || 0)
    )
  }, [selectedCalendarIds, rawEventsByCal, displayDays])

  const handleDisplayDays = (days) => {
    setDisplayDays(days)
    eventListRef.current?.scrollTo({ top: 0 })
  }

  const handleSaveSettings = ({ calendars: updatedCals, piIp: newPiIp }) => {
    setCalendars(updatedCals)
    setPiIp(newPiIp)
  }

  const allSelected = selectedCalendarIds.size === calendars.length

  return (
    <div className="flex flex-col gap-6 max-w-5xl w-full mx-auto">
      {/* View Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 pb-2 border-b border-slate-200 dark:border-white/[0.08]">
        <div>
          <h2 className="text-xl font-bold text-slate-900 dark:text-white tracking-tight">
            Lịch trình & Google Calendar
          </h2>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Quản lý các nguồn iCal, chọn lịch cần hiển thị và đồng bộ màn hình gương
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => fetchAllCalendars(calendars)}
            disabled={isLoading}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-slate-200 bg-white hover:bg-slate-50 text-slate-700 dark:border-white/10 dark:bg-white/[0.04] dark:hover:bg-white/[0.08] dark:text-slate-200 text-xs font-medium cursor-pointer"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin text-cyan-500' : ''}`} />
            <span>Làm mới</span>
          </button>

          <button
            onClick={() => setIsModalOpen(true)}
            className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-cyan-600 hover:bg-cyan-500 text-white dark:bg-cyan-500 dark:hover:bg-cyan-400 dark:text-slate-950 text-xs font-semibold shadow-md cursor-pointer"
          >
            <Settings className="w-3.5 h-3.5" />
            <span>Cài đặt nguồn iCal</span>
          </button>
        </div>
      </div>

      {/* Main 2-Column Content */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Column (8 cols): Event Timeline Stream */}
        <div className="lg:col-span-8 flex flex-col gap-4">
          {/* Quick Filter Bar */}
          <div className="p-4 rounded-xl border bg-white border-slate-200 shadow-sm dark:bg-[#0d1017]/90 dark:border-white/[0.08] flex flex-col gap-2.5">
            <div className="flex items-center justify-between text-xs text-slate-600 dark:text-slate-400">
              <span className="flex items-center gap-1.5 font-semibold text-slate-800 dark:text-slate-200">
                <Filter className="w-3.5 h-3.5 text-cyan-600 dark:text-cyan-400" />
                <span>Chọn lịch hiển thị trên danh sách:</span>
              </span>
              {!allSelected && (
                <button
                  onClick={handleSelectAll}
                  className="text-cyan-600 dark:text-cyan-400 hover:underline cursor-pointer text-xs font-medium"
                >
                  Bật tất cả ({calendars.length})
                </button>
              )}
            </div>

            <div className="flex flex-wrap items-center gap-2">
              {calendars.map((cal) => {
                const isChecked = selectedCalendarIds.has(cal.id)

                return (
                  <button
                    key={cal.id}
                    onClick={() => handleToggleFilter(cal.id)}
                    className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs transition-all cursor-pointer border ${
                      isChecked
                        ? 'border-slate-300 bg-slate-100 text-slate-800 shadow-sm dark:border-white/20 dark:bg-white/[0.08] dark:text-slate-100'
                        : 'border-slate-200 bg-slate-50 text-slate-400 hover:text-slate-700 dark:border-white/[0.05] dark:bg-white/[0.01] dark:text-slate-500 dark:hover:text-slate-300'
                    }`}
                  >
                    <span
                      className="w-2.5 h-2.5 rounded-full"
                      style={{
                        backgroundColor: cal.color,
                        boxShadow: isChecked ? `0 0 6px ${cal.color}` : 'none',
                        opacity: isChecked ? 1 : 0.4,
                      }}
                    />
                    <span className="font-semibold">{cal.name}</span>
                  </button>
                )
              })}
            </div>
          </div>

          {/* Timeline Cards */}
          <div className="min-w-0 rounded-2xl border bg-white border-slate-200 shadow-sm dark:bg-[#0d1017]/90 dark:border-white/[0.08] p-5 flex flex-col gap-3">
            <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-slate-100 dark:border-white/[0.06]">
              <div className="flex flex-wrap items-center gap-3">
                <h3 id="calendar-list-heading" className="text-xs font-bold text-slate-800 dark:text-slate-200">
                  Lịch từ hôm nay
                </h3>
                <div role="group" aria-label="Số ngày hiển thị lịch" className="flex items-center gap-1.5">
                  {[7, 14, 30].map((days) => (
                    <button
                      key={days}
                      type="button"
                      aria-pressed={displayDays === days}
                      aria-controls="calendar-event-list"
                      onClick={() => handleDisplayDays(days)}
                      className={`min-h-9 px-3 rounded-lg border text-xs font-semibold cursor-pointer transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cyan-600 dark:focus-visible:outline-cyan-400 ${displayDays === days
                        ? 'border-cyan-600 bg-cyan-600 text-white dark:border-cyan-400 dark:bg-cyan-400 dark:text-slate-950'
                        : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-100 dark:border-white/15 dark:bg-transparent dark:text-slate-300 dark:hover:bg-white/10'
                      }`}
                    >
                      {days} ngày
                    </button>
                  ))}
                </div>
                <span aria-live="polite" className="text-xs text-slate-500 dark:text-slate-400">
                  {visibleEvents.length} buổi
                </span>
              </div>
              <span className="text-[11px] text-slate-400 tabular-nums">
                {isLoading ? 'Đang tải...' : lastSyncTime ? `Đồng bộ lúc ${lastSyncTime}` : 'Chưa đồng bộ'}
              </span>
            </div>

            {calendarErrors.length > 0 && (
              <div role="alert" className="text-sm text-red-600 dark:text-red-400">
                {calendarErrors.map((message, index) => <p key={index}>{message}</p>)}
              </div>
            )}

            <div
              id="calendar-event-list"
              ref={eventListRef}
              role="region"
              aria-labelledby="calendar-list-heading"
              aria-busy={isLoading}
              tabIndex={0}
              className="max-h-[min(60vh,32rem)] overflow-y-auto overscroll-contain pr-2 [scrollbar-gutter:stable] rounded-lg focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cyan-600 dark:focus-visible:outline-cyan-400"
            >
            {visibleEvents.length === 0 ? (
              <div className="py-12 px-4 rounded-xl border border-dashed border-slate-200 dark:border-white/10 text-center">
                <CalendarIcon className="w-10 h-10 text-slate-400 dark:text-slate-600 mx-auto mb-2" />
                <p className="text-sm font-semibold text-slate-700 dark:text-slate-300">
                  {isLoading ? 'Đang tải sự kiện...' : calendarErrors.length > 0 ? 'Chưa tải được danh sách sự kiện' : `Không có lịch trong ${displayDays} ngày tới`}
                </p>
                <p className="text-xs text-slate-500 mt-1">
                  {calendarErrors.length > 0 ? 'Khắc phục lỗi ở trên rồi bấm Làm mới để thử lại.' : 'Kiểm tra các lịch đang bật hoặc thêm nguồn lịch mới.'}
                </p>
              </div>
            ) : (
              <div className="flex flex-col gap-3">
                {visibleEvents.map((evt, idx) => {
                  const timingLabel = formatEventTiming(new Date(evt.start), evt.isAllDay)
                  const eventColor = evt.color || '#06b6d4'

                  return (
                    <div
                      key={evt.id || idx}
                      className="group relative flex items-start gap-3.5 p-3.5 rounded-xl border border-slate-200 bg-slate-50/70 hover:bg-slate-100 dark:border-white/[0.06] dark:bg-white/[0.02] dark:hover:bg-white/[0.04] transition-all"
                    >
                      {/* Timeline dot */}
                      <div className="mt-1 flex flex-col items-center">
                        <div
                          className="w-3 h-3 rounded-full"
                          style={{
                            backgroundColor: eventColor,
                            boxShadow: `0 0 8px ${eventColor}66`,
                          }}
                        />
                        {idx < visibleEvents.length - 1 && (
                          <div className="w-0.5 h-10 bg-slate-200 dark:bg-white/10 mt-1" />
                        )}
                      </div>

                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between gap-2">
                          <h4 className="text-sm font-semibold text-slate-800 dark:text-slate-100 truncate">
                            {evt.title}
                          </h4>
                          <span className="text-[11px] font-medium text-cyan-700 bg-cyan-50 border-cyan-200 dark:text-cyan-300 dark:bg-cyan-500/10 dark:border-cyan-500/20 tabular-nums shrink-0 px-2.5 py-0.5 rounded-full border">
                            {timingLabel}
                          </span>
                        </div>

                        <div className="flex items-center gap-2 mt-1.5">
                          <span
                            className="text-[10px] px-2 py-0.5 rounded-md font-medium border"
                            style={{
                              backgroundColor: `${eventColor}15`,
                              color: eventColor,
                              borderColor: `${eventColor}33`,
                            }}
                          >
                            {evt.calendarName || 'Lịch'}
                          </span>

                          {evt.location && (
                            <div className="flex items-center gap-1 text-xs text-slate-500 dark:text-slate-400 truncate">
                              <MapPin className="w-3.5 h-3.5 text-slate-400 dark:text-slate-500 shrink-0" />
                              <span className="truncate">{evt.location}</span>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
            </div>
          </div>
        </div>

        {/* Right Column (4 cols): Configured Feeds Summary & Mirror Sync */}
        <div className="lg:col-span-4 flex flex-col gap-4">
          {/* Active Feeds Status Card */}
          <div className="rounded-2xl border bg-white border-slate-200 shadow-sm dark:bg-[#0d1017]/90 dark:border-white/[0.08] p-5 flex flex-col gap-3.5">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-slate-900 dark:text-white">
                Nguồn lịch đã cấu hình
              </h3>
              <button
                onClick={() => setIsModalOpen(true)}
                className="text-xs text-cyan-600 dark:text-cyan-400 hover:underline font-medium cursor-pointer"
              >
                + Thêm
              </button>
            </div>

            <div className="flex flex-col gap-2">
              {calendars.map((cal) => (
                <div
                  key={cal.id}
                  className="flex items-center justify-between p-2.5 rounded-xl border border-slate-100 bg-slate-50/50 dark:border-white/[0.04] dark:bg-white/[0.02]"
                >
                  <div className="flex items-center gap-2.5 min-w-0">
                    <span
                      className="w-2.5 h-2.5 rounded-full shrink-0"
                      style={{ backgroundColor: cal.color }}
                    />
                    <div className="truncate">
                      <span className="text-xs font-semibold text-slate-800 dark:text-slate-200 block truncate">
                        {cal.name}
                      </span>
                      <span className="text-[10px] text-slate-400 font-mono block truncate">
                        {cal.url ? 'iCal URL sẵn sàng' : 'Chưa nhập URL'}
                      </span>
                    </div>
                  </div>

                  <button
                    onClick={() => handleToggleFilter(cal.id)}
                    className="p-1 text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 cursor-pointer"
                    title={cal.enabled ? 'Đang bật' : 'Đang tắt'}
                  >
                    {cal.enabled ? (
                      <Eye className="w-3.5 h-3.5 text-cyan-600 dark:text-cyan-400" />
                    ) : (
                      <EyeOff className="w-3.5 h-3.5 text-slate-400" />
                    )}
                  </button>
                </div>
              ))}
            </div>

            {/* Mirror sync hardware box */}
            <div className="mt-2 pt-3 border-t border-slate-100 dark:border-white/[0.06] flex flex-col gap-1.5 text-xs text-slate-500 dark:text-slate-400">
              <div className="flex items-center gap-1.5 font-semibold text-slate-700 dark:text-slate-300">
                <Server className="w-3.5 h-3.5 text-emerald-500" />
                <span>Gương thật (MagicMirror Pi)</span>
              </div>
              <p className="text-[11px] leading-relaxed">
                Các lịch được bật sẽ đồng bộ trực tiếp sang module calendar ở góc dưới bên trái của gương tại IP <code className="font-mono text-cyan-600 dark:text-cyan-400">{piIp}</code>.
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Modal */}
      <CalendarSettingsModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        calendars={calendars}
        piIp={piIp}
        onSave={handleSaveSettings}
      />
    </div>
  )
}

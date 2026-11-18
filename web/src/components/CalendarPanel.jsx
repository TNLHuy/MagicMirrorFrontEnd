import React, { useState, useEffect, useMemo } from 'react'
import {
  Calendar as CalendarIcon,
  Settings,
  RefreshCw,
  MapPin,
  CheckCircle2,
  Filter,
} from 'lucide-react'
import CalendarSettingsModal from './CalendarSettingsModal'
import { parseICS, formatEventTiming } from '../utils/icsParser'
import { DEFAULT_CALENDARS, FALLBACK_CALENDAR_EVENTS } from '../data/mockData'

export default function CalendarPanel() {
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

  // Set of calendar IDs currently enabled to show
  const [selectedCalendarIds, setSelectedCalendarIds] = useState(() => {
    return new Set(
      calendars.filter((c) => c.enabled !== false).map((c) => c.id)
    )
  })

  const [rawEventsByCal, setRawEventsByCal] = useState({})
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [lastSyncTime, setLastSyncTime] = useState(null)

  // Sync selectedCalendarIds whenever calendars change
  useEffect(() => {
    setSelectedCalendarIds(
      new Set(calendars.filter((c) => c.enabled !== false).map((c) => c.id))
    )
  }, [calendars])

  // Fetch all calendars
  const fetchAllCalendars = async (calsToFetch = calendars) => {
    setIsLoading(true)
    const newEventsMap = {}

    for (const cal of calsToFetch) {
      if (!cal.url || !cal.url.trim()) {
        const sampleEvents = FALLBACK_CALENDAR_EVENTS.filter(
          (e) => e.calendarId === cal.id
        ).map((e) => ({ ...e, color: cal.color, calendarName: cal.name }))
        newEventsMap[cal.id] = sampleEvents
        continue
      }

      try {
        const res = await fetch(cal.url.trim()).catch(() => null)
        if (res && res.ok) {
          const text = await res.text()
          const parsed = parseICS(text, cal)
          newEventsMap[cal.id] = parsed
        } else {
          const sampleEvents = FALLBACK_CALENDAR_EVENTS.filter(
            (e) => e.calendarId === cal.id || cal.url.includes('holiday')
          ).map((e) => ({ ...e, color: cal.color, calendarName: cal.name }))
          newEventsMap[cal.id] = sampleEvents.length > 0 ? sampleEvents : []
        }
      } catch {
        const sampleEvents = FALLBACK_CALENDAR_EVENTS.filter(
          (e) => e.calendarId === cal.id
        ).map((e) => ({ ...e, color: cal.color, calendarName: cal.name }))
        newEventsMap[cal.id] = sampleEvents
      }
    }

    setRawEventsByCal(newEventsMap)
    setLastSyncTime(new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }))
    setIsLoading(false)
  }

  useEffect(() => {
    fetchAllCalendars(calendars)
  }, [calendars])

  // Toggle calendar filter chip
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

  // Filter and merge events from selected calendars
  const visibleEvents = useMemo(() => {
    const combined = []

    for (const calId of selectedCalendarIds) {
      const evts = rawEventsByCal[calId] || []
      combined.push(...evts)
    }

    if (combined.length === 0) {
      const fallbacks = FALLBACK_CALENDAR_EVENTS.filter((e) =>
        selectedCalendarIds.has(e.calendarId)
      )
      combined.push(...fallbacks)
    }

    return combined.sort(
      (a, b) => (new Date(a.start).getTime() || 0) - (new Date(b.start).getTime() || 0)
    )
  }, [selectedCalendarIds, rawEventsByCal])

  const handleSaveSettings = ({ calendars: updatedCals, piIp: newPiIp }) => {
    setCalendars(updatedCals)
    setPiIp(newPiIp)
    fetchAllCalendars(updatedCals)
  }

  const allSelected = selectedCalendarIds.size === calendars.length

  return (
    <section className="rounded-2xl border bg-white border-slate-200 shadow-sm dark:bg-[#0d1017]/90 dark:border-white/[0.08] dark:shadow-xl p-5 md:p-6 backdrop-blur-sm flex flex-col gap-4 transition-colors">
      {/* Calendar Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-600 dark:text-emerald-400">
            <CalendarIcon className="w-4 h-4" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base font-semibold text-slate-900 dark:text-white tracking-tight">
                Lịch trình
              </h2>
              <span className="text-[11px] font-medium px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 border border-emerald-500/30">
                {calendars.length} Lịch
              </span>
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Đồng bộ Google Calendar & hiển thị màn hình gương
            </p>
          </div>
        </div>

        {/* Action icons */}
        <div className="flex items-center gap-1.5">
          <button
            onClick={() => fetchAllCalendars(calendars)}
            disabled={isLoading}
            className="p-1.5 rounded-lg text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-white/[0.05] transition-colors cursor-pointer"
            title="Làm mới đồng bộ lịch"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin text-cyan-500' : ''}`} />
          </button>
          <button
            onClick={() => setIsModalOpen(true)}
            className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 border border-slate-200 dark:bg-white/[0.04] dark:hover:bg-white/[0.08] dark:border-white/[0.08] text-slate-700 dark:text-slate-200 text-xs font-medium transition-colors cursor-pointer"
            title="Thêm & Quản lý các link Google Calendar"
          >
            <Settings className="w-3.5 h-3.5 text-cyan-600 dark:text-cyan-400" />
            <span className="hidden sm:inline">Quản lý link</span>
          </button>
        </div>
      </div>

      {/* Calendar Selection Chips */}
      <div className="flex flex-col gap-1.5 pt-1">
        <div className="flex items-center justify-between text-[11px] text-slate-500 dark:text-slate-400">
          <span className="flex items-center gap-1 font-medium">
            <Filter className="w-3 h-3 text-cyan-600 dark:text-cyan-400" />
            <span>Chọn lịch hiển thị:</span>
          </span>
          {!allSelected && (
            <button
              onClick={handleSelectAll}
              className="text-cyan-600 dark:text-cyan-400 hover:underline cursor-pointer text-[10px]"
            >
              Bật tất cả
            </button>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-1.5">
          {calendars.map((cal) => {
            const isChecked = selectedCalendarIds.has(cal.id)

            return (
              <button
                key={cal.id}
                onClick={() => handleToggleFilter(cal.id)}
                className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs transition-all cursor-pointer border ${
                  isChecked
                    ? 'border-slate-300 bg-slate-100 text-slate-800 shadow-sm dark:border-white/20 dark:bg-white/[0.08] dark:text-slate-100'
                    : 'border-slate-200 bg-slate-50 text-slate-400 hover:text-slate-700 dark:border-white/[0.05] dark:bg-white/[0.01] dark:text-slate-500 dark:hover:text-slate-300'
                }`}
                title={isChecked ? `Đang bật ${cal.name} (Bấm để ẩn)` : `Đang ẩn ${cal.name} (Bấm để bật)`}
              >
                <span
                  className="w-2 h-2 rounded-full transition-transform"
                  style={{
                    backgroundColor: cal.color,
                    boxShadow: isChecked ? `0 0 6px ${cal.color}` : 'none',
                    opacity: isChecked ? 1 : 0.4,
                  }}
                />
                <span className="font-medium text-[11px]">{cal.name}</span>
              </button>
            )
          })}
        </div>
      </div>

      {/* Events Timeline */}
      <div className="flex flex-col gap-2.5 pt-1">
        {visibleEvents.length === 0 ? (
          <div className="py-8 px-4 rounded-xl border border-dashed border-slate-200 dark:border-white/10 text-center">
            <CalendarIcon className="w-8 h-8 text-slate-400 dark:text-slate-600 mx-auto mb-2" />
            <p className="text-xs text-slate-500 dark:text-slate-400">Không có sự kiện nào cho các lịch đang chọn</p>
            <button
              onClick={() => setIsModalOpen(true)}
              className="mt-2 text-xs text-cyan-600 dark:text-cyan-400 hover:underline cursor-pointer"
            >
              Thêm hoặc bật link lịch Google
            </button>
          </div>
        ) : (
          visibleEvents.slice(0, 5).map((evt, idx) => {
            const timingLabel = formatEventTiming(new Date(evt.start), evt.isAllDay)
            const eventColor = evt.color || '#06b6d4'

            return (
              <div
                key={evt.id || idx}
                className="group relative flex items-start gap-3 p-3 rounded-xl border border-slate-200 bg-slate-50/70 hover:bg-slate-100 dark:border-white/[0.06] dark:bg-white/[0.02] dark:hover:bg-white/[0.04] transition-all"
              >
                {/* Colored Timeline Indicator */}
                <div className="mt-1 flex flex-col items-center">
                  <div
                    className="w-2.5 h-2.5 rounded-full"
                    style={{
                      backgroundColor: eventColor,
                      boxShadow: `0 0 8px ${eventColor}66`,
                    }}
                  />
                  {idx < Math.min(visibleEvents.length, 5) - 1 && (
                    <div className="w-0.5 h-8 bg-slate-200 dark:bg-white/10 mt-1" />
                  )}
                </div>

                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs font-semibold text-slate-800 dark:text-slate-100 truncate">
                      {evt.title}
                    </span>
                    <span className="text-[10px] font-medium text-cyan-700 bg-cyan-50 border-cyan-200 dark:text-cyan-300 dark:bg-cyan-500/10 dark:border-cyan-500/20 tabular-nums shrink-0 px-2 py-0.5 rounded border">
                      {timingLabel}
                    </span>
                  </div>

                  <div className="flex items-center gap-2 mt-1">
                    {/* Calendar origin badge */}
                    <span
                      className="text-[10px] px-1.5 py-0.2 rounded font-medium border"
                      style={{
                        backgroundColor: `${eventColor}15`,
                        color: eventColor,
                        borderColor: `${eventColor}33`,
                      }}
                    >
                      {evt.calendarName || 'Lịch'}
                    </span>

                    {evt.location && (
                      <div className="flex items-center gap-1 text-[11px] text-slate-500 dark:text-slate-400 truncate">
                        <MapPin className="w-3 h-3 text-slate-400 dark:text-slate-500 shrink-0" />
                        <span className="truncate">{evt.location}</span>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )
          })
        )}
      </div>

      {/* Sync Footer Note */}
      <div className="pt-2 border-t border-slate-200 dark:border-white/[0.06] flex items-center justify-between text-[11px] text-slate-500 dark:text-slate-400">
        <div className="flex items-center gap-1.5 truncate">
          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400 shrink-0" />
          <span className="truncate">
            Đồng bộ Smart Mirror: <span className="text-slate-700 dark:text-slate-300 font-mono text-[10px]">{piIp}</span>
          </span>
        </div>
        <div className="shrink-0 text-slate-400 dark:text-slate-500 tabular-nums">
          {lastSyncTime ? `Đã đồng bộ ${lastSyncTime}` : 'Sẵn sàng'}
        </div>
      </div>

      {/* Multi-Calendar Settings Modal */}
      <CalendarSettingsModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        calendars={calendars}
        piIp={piIp}
        onSave={handleSaveSettings}
      />
    </section>
  )
}

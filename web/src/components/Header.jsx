import React, { useState, useEffect } from 'react'
import { Sparkles, Wifi, Cpu, RotateCw, Sun, Moon } from 'lucide-react'

export default function Header({ onRefresh, isRefreshing, theme, onToggleTheme }) {
  const [currentTime, setCurrentTime] = useState(new Date())

  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 1000)
    return () => clearInterval(timer)
  }, [])

  const formattedTime = currentTime.toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  })

  const formattedDate = currentTime.toLocaleDateString('vi-VN', {
    weekday: 'long',
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })

  return (
    <header className="border-b bg-white/80 border-slate-200 dark:bg-[#090b11]/80 dark:border-white/[0.08] backdrop-blur-md sticky top-0 z-40 px-4 lg:px-8 py-3.5 transition-colors">
      <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        {/* Brand & Companion title */}
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center text-cyan-600 dark:text-cyan-400 shadow-[0_0_15px_rgba(6,182,212,0.15)]">
            <Sparkles className="w-5 h-5 animate-pulse" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-lg font-semibold text-slate-900 dark:text-white tracking-tight">
                Web_MagicMirror
              </h1>
              <span className="text-[11px] font-medium px-2 py-0.5 rounded-full bg-cyan-500/15 text-cyan-700 dark:text-cyan-300 border border-cyan-500/30">
                Companion Hub
              </span>
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Smart Mirror IoT Dashboard & Photo Gallery
            </p>
          </div>
        </div>

        {/* Live Telemetry & Actions */}
        <div className="flex flex-wrap items-center gap-2.5 sm:gap-4 w-full md:w-auto justify-between md:justify-end">
          {/* Physical Mirror status */}
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-100 border border-slate-200 dark:bg-white/[0.03] dark:border-white/[0.06] text-xs">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
            </span>
            <Wifi className="w-3.5 h-3.5 text-slate-500 dark:text-slate-400" />
            <span className="text-slate-600 dark:text-slate-300">Mirror</span>
            <span className="text-[11px] text-emerald-600 dark:text-emerald-400 font-medium">192.168.1.105</span>
          </div>

          {/* ESP32 LED status */}
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-100 border border-slate-200 dark:bg-white/[0.03] dark:border-white/[0.06] text-xs">
            <Cpu className="w-3.5 h-3.5 text-cyan-600 dark:text-cyan-400" />
            <span className="text-slate-600 dark:text-slate-300">ESP32</span>
            <span className="text-[11px] text-cyan-600 dark:text-cyan-400 font-medium">Ready</span>
          </div>

          {/* Clock & Date */}
          <div className="hidden sm:flex flex-col items-end text-right px-2">
            <span className="text-sm font-semibold text-slate-800 dark:text-slate-100 tabular-nums tracking-wider">
              {formattedTime}
            </span>
            <span className="text-[11px] text-slate-500 dark:text-slate-400">{formattedDate}</span>
          </div>

          {/* Light / Dark Mode Toggle */}
          <button
            onClick={onToggleTheme}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-medium transition-colors cursor-pointer bg-slate-100 hover:bg-slate-200 border-slate-300 text-slate-700 dark:bg-white/[0.05] dark:hover:bg-white/[0.1] dark:border-white/10 dark:text-slate-200"
            title={theme === 'dark' ? 'Chuyển sang giao diện Sáng' : 'Chuyển sang giao diện Tối'}
          >
            {theme === 'dark' ? (
              <>
                <Sun className="w-3.5 h-3.5 text-amber-400" />
                <span className="hidden sm:inline">Giao diện Sáng</span>
              </>
            ) : (
              <>
                <Moon className="w-3.5 h-3.5 text-indigo-600" />
                <span className="hidden sm:inline">Giao diện Tối</span>
              </>
            )}
          </button>

          {/* Refresh sync button */}
          <button
            onClick={onRefresh}
            disabled={isRefreshing}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-cyan-500/10 hover:bg-cyan-500/20 active:bg-cyan-500/30 border border-cyan-500/30 text-cyan-700 dark:text-cyan-300 text-xs font-medium transition-all duration-150 disabled:opacity-50 cursor-pointer"
            title="Đồng bộ gương & thiết bị"
          >
            <RotateCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin text-cyan-500' : ''}`} />
            <span className="hidden sm:inline">{isRefreshing ? 'Đang đồng bộ...' : 'Đồng bộ'}</span>
          </button>
        </div>
      </div>
    </header>
  )
}

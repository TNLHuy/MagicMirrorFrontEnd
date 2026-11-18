import React from 'react'
import {
  Sparkles,
  Cpu,
  Calendar,
  Camera,
  Sun,
  Moon,
  RotateCw,
  Wifi,
  ChevronRight,
} from 'lucide-react'

export default function Sidebar({
  activeTab,
  onTabChange,
  theme,
  onToggleTheme,
  onRefresh,
  isRefreshing,
  photoCount,
  calendarCount,
  deviceCount,
}) {
  const navItems = [
    {
      id: 'iot',
      label: 'Thiết bị IoT',
      sublabel: 'Đèn ESP32 & Smart Home',
      icon: Cpu,
      badge: `${deviceCount} Thiết bị`,
      color: 'cyan',
    },
    {
      id: 'calendar',
      label: 'Lịch trình',
      sublabel: 'Google Calendar Sync',
      icon: Calendar,
      badge: `${calendarCount} Lịch`,
      color: 'emerald',
    },
    {
      id: 'gallery',
      label: 'Kho ảnh gương',
      sublabel: 'Webcam snapshot & QR',
      icon: Camera,
      badge: `${photoCount} Ảnh`,
      color: 'violet',
    },
  ]

  return (
    <>
      {/* Desktop Left Sidebar (>= 1024px) */}
      <aside className="hidden lg:flex w-72 shrink-0 flex-col justify-between border-r bg-white border-slate-200 dark:bg-[#0a0d14] dark:border-white/[0.08] p-5 h-screen sticky top-0 transition-colors z-30">
        <div className="flex flex-col gap-6">
          {/* Logo & Brand Title */}
          <div className="flex items-center gap-3 px-2 py-1">
            <div className="w-10 h-10 rounded-xl bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center text-cyan-600 dark:text-cyan-400 shadow-[0_0_15px_rgba(6,182,212,0.15)]">
              <Sparkles className="w-5 h-5 animate-pulse" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-base font-bold text-slate-900 dark:text-white tracking-tight">
                  MagicMirror
                </h1>
                <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-cyan-500/15 text-cyan-700 dark:text-cyan-300 border border-cyan-500/30">
                  Hub
                </span>
              </div>
              <p className="text-[11px] text-slate-500 dark:text-slate-400">Trợ lý gương thông minh</p>
            </div>
          </div>

          {/* Navigation Links */}
          <nav className="flex flex-col gap-1.5" aria-label="Main Navigation">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500 px-3 mb-1">
              Danh mục quản lý
            </span>
            {navItems.map((item) => {
              const Icon = item.icon
              const isActive = activeTab === item.id

              return (
                <button
                  key={item.id}
                  onClick={() => onTabChange(item.id)}
                  className={`group flex items-center justify-between p-3 rounded-xl border text-left transition-all cursor-pointer ${
                    isActive
                      ? 'bg-slate-100 border-slate-300 text-slate-900 shadow-sm dark:bg-white/[0.06] dark:border-white/15 dark:text-white dark:shadow-[0_0_15px_rgba(6,182,212,0.1)]'
                      : 'border-transparent text-slate-600 hover:text-slate-900 hover:bg-slate-50 dark:text-slate-400 dark:hover:text-slate-200 dark:hover:bg-white/[0.03]'
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <div
                      className={`w-8 h-8 rounded-lg flex items-center justify-center transition-colors ${
                        isActive
                          ? 'bg-cyan-500/20 text-cyan-700 dark:text-cyan-300 border border-cyan-500/40'
                          : 'bg-slate-100 dark:bg-white/[0.04] text-slate-500 dark:text-slate-400 group-hover:text-slate-800 dark:group-hover:text-slate-200'
                      }`}
                    >
                      <Icon className="w-4 h-4" />
                    </div>
                    <div>
                      <span className="text-xs font-semibold block leading-tight">{item.label}</span>
                      <span className="text-[10px] text-slate-400 dark:text-slate-500 block leading-tight mt-0.5">
                        {item.sublabel}
                      </span>
                    </div>
                  </div>

                  <div className="flex items-center gap-1.5">
                    <span
                      className={`text-[10px] font-medium px-2 py-0.5 rounded-full border ${
                        isActive
                          ? 'bg-cyan-50 text-cyan-700 border-cyan-200 dark:bg-cyan-500/15 dark:text-cyan-300 dark:border-cyan-500/30'
                          : 'bg-slate-100 text-slate-500 border-slate-200 dark:bg-white/[0.03] dark:text-slate-400 dark:border-white/[0.06]'
                      }`}
                    >
                      {item.badge}
                    </span>
                    <ChevronRight
                      className={`w-3.5 h-3.5 transition-transform ${
                        isActive
                          ? 'text-cyan-600 dark:text-cyan-400 translate-x-0.5'
                          : 'text-slate-300 dark:text-slate-600 opacity-0 group-hover:opacity-100'
                      }`}
                    />
                  </div>
                </button>
              )
            })}
          </nav>
        </div>

        {/* Sidebar Footer Area */}
        <div className="flex flex-col gap-3 pt-4 border-t border-slate-200 dark:border-white/[0.08]">
          {/* Mirror Connection telemetry */}
          <div className="flex items-center justify-between px-3 py-2 rounded-xl bg-slate-50 dark:bg-white/[0.02] border border-slate-200 dark:border-white/[0.06] text-xs">
            <div className="flex items-center gap-2">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
              </span>
              <Wifi className="w-3.5 h-3.5 text-slate-500 dark:text-slate-400" />
              <span className="text-slate-700 dark:text-slate-300 text-[11px] font-medium">Gương Pi 5</span>
            </div>
            <span className="text-[10px] text-emerald-600 dark:text-emerald-400 font-mono">192.168.1.105</span>
          </div>

          {/* Quick Controls: Light/Dark Mode + Refresh Sync */}
          <div className="grid grid-cols-2 gap-2">
            <button
              onClick={onToggleTheme}
              className="flex items-center justify-center gap-1.5 py-2 px-3 rounded-xl border text-xs font-medium transition-colors cursor-pointer bg-slate-100 hover:bg-slate-200 border-slate-300 text-slate-700 dark:bg-white/[0.04] dark:hover:bg-white/[0.08] dark:border-white/10 dark:text-slate-200"
              title={theme === 'dark' ? 'Chuyển sang giao diện Sáng' : 'Chuyển sang giao diện Tối'}
            >
              {theme === 'dark' ? (
                <>
                  <Sun className="w-3.5 h-3.5 text-amber-400" />
                  <span>Sáng</span>
                </>
              ) : (
                <>
                  <Moon className="w-3.5 h-3.5 text-indigo-600" />
                  <span>Tối</span>
                </>
              )}
            </button>

            <button
              onClick={onRefresh}
              disabled={isRefreshing}
              className="flex items-center justify-center gap-1.5 py-2 px-3 rounded-xl bg-cyan-500/10 hover:bg-cyan-500/20 active:bg-cyan-500/30 border border-cyan-500/30 text-cyan-700 dark:text-cyan-300 text-xs font-medium transition-all disabled:opacity-50 cursor-pointer"
              title="Đồng bộ gương & thiết bị"
            >
              <RotateCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin text-cyan-500' : ''}`} />
              <span>{isRefreshing ? 'Sync...' : 'Đồng bộ'}</span>
            </button>
          </div>
        </div>
      </aside>

      {/* Mobile Sticky Navigation Header & Bottom Bar (< 1024px) */}
      <header className="lg:hidden sticky top-0 z-40 border-b bg-white/90 border-slate-200 dark:bg-[#0a0d14]/90 dark:border-white/[0.08] backdrop-blur-md px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center text-cyan-600 dark:text-cyan-400">
            <Sparkles className="w-4 h-4" />
          </div>
          <div>
            <h1 className="text-sm font-bold text-slate-900 dark:text-white leading-tight">MagicMirror</h1>
            <p className="text-[10px] text-slate-500 dark:text-slate-400 leading-tight">Companion Hub</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={onToggleTheme}
            className="p-1.5 rounded-lg border border-slate-300 dark:border-white/10 text-slate-700 dark:text-slate-200 bg-slate-100 dark:bg-white/[0.05] cursor-pointer"
          >
            {theme === 'dark' ? <Sun className="w-3.5 h-3.5 text-amber-400" /> : <Moon className="w-3.5 h-3.5 text-indigo-600" />}
          </button>
          <button
            onClick={onRefresh}
            disabled={isRefreshing}
            className="p-1.5 rounded-lg border border-cyan-500/30 text-cyan-700 dark:text-cyan-300 bg-cyan-500/10 cursor-pointer"
          >
            <RotateCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </header>

      {/* Mobile Bottom Navigation Bar (< 1024px) */}
      <nav
        className="lg:hidden fixed bottom-0 left-0 right-0 z-40 border-t bg-white/95 border-slate-200 dark:bg-[#0a0d14]/95 dark:border-white/[0.08] backdrop-blur-md px-2 py-2 flex items-center justify-around shadow-lg"
        aria-label="Mobile Navigation"
      >
        {navItems.map((item) => {
          const Icon = item.icon
          const isActive = activeTab === item.id

          return (
            <button
              key={item.id}
              onClick={() => onTabChange(item.id)}
              className={`flex flex-col items-center gap-1 py-1.5 px-3 rounded-xl transition-all cursor-pointer ${
                isActive
                  ? 'text-cyan-600 dark:text-cyan-400 font-semibold'
                  : 'text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200'
              }`}
            >
              <div
                className={`p-1 rounded-lg transition-colors ${
                  isActive ? 'bg-cyan-500/15' : 'bg-transparent'
                }`}
              >
                <Icon className="w-4 h-4" />
              </div>
              <span className="text-[10px] leading-tight">{item.label}</span>
            </button>
          )
        })}
      </nav>
    </>
  )
}

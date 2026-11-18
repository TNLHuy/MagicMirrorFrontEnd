import React, { useState } from 'react'
import { Camera, QrCode, Maximize2, Layers } from 'lucide-react'

export default function PhotoGallery({ photos, onSelectPhoto }) {
  const [viewMode, setViewMode] = useState('recent') // 'recent' | 'all'

  const displayedPhotos = viewMode === 'recent' ? photos.slice(0, 6) : photos

  return (
    <section className="rounded-2xl border bg-white border-slate-200 shadow-sm dark:bg-[#0d1017]/90 dark:border-white/[0.08] dark:shadow-xl p-5 md:p-6 backdrop-blur-sm flex flex-col gap-4 transition-colors">
      {/* Gallery Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-violet-500/10 border border-violet-500/20 flex items-center justify-center text-violet-600 dark:text-violet-400">
            <Camera className="w-4 h-4" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base font-semibold text-slate-900 dark:text-white tracking-tight">
                Bộ sưu tập gương thông minh
              </h2>
              <span className="text-[11px] font-mono px-2 py-0.5 rounded-full bg-violet-500/15 text-violet-700 dark:text-violet-300 border border-violet-500/30">
                {photos.length} Ảnh chụp
              </span>
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Ảnh webcam chụp từ gương với mã QR tải về điện thoại tức thì
            </p>
          </div>
        </div>

        {/* View mode toggle */}
        <div className="flex items-center gap-1 bg-slate-100 dark:bg-white/[0.04] p-1 rounded-lg border border-slate-200 dark:border-white/[0.06] text-xs">
          <button
            onClick={() => setViewMode('recent')}
            className={`px-3 py-1 rounded-md font-medium transition-all cursor-pointer ${
              viewMode === 'recent'
                ? 'bg-violet-100 text-violet-800 border border-violet-200 dark:bg-violet-500/20 dark:text-violet-300 dark:border-violet-500/40 shadow-sm'
                : 'text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200'
            }`}
          >
            Mới nhất
          </button>
          <button
            onClick={() => setViewMode('all')}
            className={`flex items-center gap-1 px-3 py-1 rounded-md font-medium transition-all cursor-pointer ${
              viewMode === 'all'
                ? 'bg-violet-100 text-violet-800 border border-violet-200 dark:bg-violet-500/20 dark:text-violet-300 dark:border-violet-500/40 shadow-sm'
                : 'text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200'
            }`}
          >
            <Layers className="w-3 h-3" />
            <span>Tất cả ({photos.length})</span>
          </button>
        </div>
      </div>

      {/* Grid of Snapshots */}
      {displayedPhotos.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-12 px-4 rounded-xl border border-dashed border-slate-200 dark:border-white/10 text-center">
          <Camera className="w-10 h-10 text-slate-400 dark:text-slate-600 mb-2" />
          <p className="text-sm font-medium text-slate-700 dark:text-slate-300">Chưa có ảnh nào được chụp</p>
          <p className="text-xs text-slate-500 mt-1">
            Hãy cất tiếng nói <strong className="text-cyan-600 dark:text-cyan-400 font-normal">"Chụp cho tôi một bức ảnh"</strong> trước gương!
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          {displayedPhotos.map((photo) => (
            <div
              key={photo.id}
              onClick={() => onSelectPhoto(photo)}
              className="group relative rounded-xl overflow-hidden border border-slate-200 bg-slate-900 dark:border-white/[0.08] aspect-[4/3] cursor-pointer transition-all duration-200 hover:border-cyan-400/50 hover:shadow-[0_0_15px_rgba(6,182,212,0.2)]"
            >
              <img
                src={photo.url}
                alt={photo.fileName}
                className="w-full h-full object-cover transition-transform duration-300 group-hover:scale-105"
                loading="lazy"
              />

              {/* Gradient Dark Overlay */}
              <div className="absolute inset-0 bg-gradient-to-t from-black/85 via-black/25 to-transparent opacity-80 group-hover:opacity-90 transition-opacity" />

              {/* Top tag & QR Pill */}
              <div className="absolute top-2 left-2 right-2 flex items-center justify-between pointer-events-none">
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-black/60 backdrop-blur-md text-slate-200 border border-white/10">
                  {photo.tag}
                </span>

                <div className="flex items-center gap-1 px-1.5 py-0.5 rounded bg-cyan-950/80 backdrop-blur-md text-cyan-300 border border-cyan-500/40 opacity-0 group-hover:opacity-100 transition-opacity text-[10px] font-medium shadow-sm">
                  <QrCode className="w-3 h-3 text-cyan-400" />
                  <span>Quét QR</span>
                </div>
              </div>

              {/* Bottom Info & Enlarge hint */}
              <div className="absolute bottom-2 left-2 right-2 flex items-end justify-between">
                <div>
                  <span className="text-[11px] font-medium text-white block truncate leading-tight">
                    {photo.formattedDate}
                  </span>
                  <span className="text-[10px] text-slate-300 font-mono block">
                    {photo.size}
                  </span>
                </div>

                <div className="w-6 h-6 rounded-md bg-white/10 backdrop-blur-md flex items-center justify-center text-white opacity-0 group-hover:opacity-100 transition-opacity">
                  <Maximize2 className="w-3 h-3" />
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}

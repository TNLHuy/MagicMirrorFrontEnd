import React, { useState } from 'react'
import {
  Camera,
  QrCode,
  Maximize2,
  Layers,
  Search,
  Filter,
  Download,
  Calendar,
} from 'lucide-react'

export default function GalleryView({ photos, onSelectPhoto, onRefresh, isLoading }) {
  const [filterTag, setFilterTag] = useState('all') // 'all' | 'Webcam Selfie' | 'Living Room' | etc.
  const [searchQuery, setSearchQuery] = useState('')
  const [gridDensity, setGridDensity] = useState('normal') // 'normal' (3 cols) | 'dense' (4-5 cols)

  // Extract unique tags
  const tags = ['all', ...new Set(photos.map((p) => p.tag).filter(Boolean))]

  const filteredPhotos = photos.filter((photo) => {
    const matchesTag = filterTag === 'all' || photo.tag === filterTag
    const matchesSearch =
      photo.fileName.toLowerCase().includes(searchQuery.toLowerCase()) ||
      photo.formattedDate.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (photo.tag && photo.tag.toLowerCase().includes(searchQuery.toLowerCase()))
    return matchesTag && matchesSearch
  })

  return (
    <div className="flex flex-col gap-6 max-w-6xl w-full mx-auto">
      {/* View Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 pb-2 border-b border-slate-200 dark:border-white/[0.08]">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-xl font-bold text-slate-900 dark:text-white tracking-tight">
              Kho ảnh gương thông minh
            </h2>
            <span className="text-xs font-mono px-2.5 py-0.5 rounded-full bg-violet-500/15 text-violet-700 dark:text-violet-300 border border-violet-500/30">
              {photos.length} Ảnh snapshot
            </span>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Lưu trữ ảnh webcam chụp từ gương qua lệnh giọng nói kèm mã QR tải về điện thoại ngay tức khắc
          </p>
        </div>

        {/* Search Input */}
        <div className="relative flex items-center w-full sm:w-64">
          <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 pointer-events-none" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Tìm theo ngày, tên file..."
            className="w-full text-xs pl-8 pr-3 py-1.5 rounded-xl border border-slate-200 bg-white dark:bg-white/[0.04] dark:border-white/10 text-slate-800 dark:text-white placeholder-slate-400 outline-none focus:border-cyan-500"
          />
        </div>
      </div>

      {/* Filter and Density Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-3 p-3 rounded-xl border bg-white border-slate-200 shadow-sm dark:bg-[#0d1017]/90 dark:border-white/[0.08]">
        {/* Tag Filters */}
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-xs font-medium text-slate-500 dark:text-slate-400 flex items-center gap-1 mr-1">
            <Filter className="w-3 h-3 text-violet-600 dark:text-violet-400" />
            <span>Phân loại:</span>
          </span>
          {tags.map((tag) => (
            <button
              key={tag}
              onClick={() => setFilterTag(tag)}
              className={`px-3 py-1 rounded-full text-xs transition-all cursor-pointer border ${
                filterTag === tag
                  ? 'bg-violet-100 text-violet-800 border-violet-300 dark:bg-violet-500/20 dark:text-violet-300 dark:border-violet-500/40 font-semibold shadow-sm'
                  : 'bg-slate-50 text-slate-500 border-slate-200 hover:text-slate-800 dark:bg-white/[0.02] dark:text-slate-400 dark:border-white/[0.06] dark:hover:text-slate-200'
              }`}
            >
              {tag === 'all' ? 'Tất cả ảnh' : tag}
            </button>
          ))}
        </div>

        {/* Grid View Mode */}
        <div className="hidden sm:flex items-center gap-1 bg-slate-100 dark:bg-white/[0.04] p-1 rounded-lg border border-slate-200 dark:border-white/[0.06] text-xs">
          <button
            onClick={() => setGridDensity('normal')}
            className={`px-2.5 py-1 rounded font-medium transition-all cursor-pointer ${
              gridDensity === 'normal'
                ? 'bg-white text-slate-900 shadow-sm dark:bg-white/[0.1] dark:text-white'
                : 'text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200'
            }`}
          >
            Lưới lớn
          </button>
          <button
            onClick={() => setGridDensity('dense')}
            className={`px-2.5 py-1 rounded font-medium transition-all cursor-pointer ${
              gridDensity === 'dense'
                ? 'bg-white text-slate-900 shadow-sm dark:bg-white/[0.1] dark:text-white'
                : 'text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200'
            }`}
          >
            Lưới nhỏ gọn
          </button>
        </div>
      </div>

      {/* Grid of Snapshots */}
      {isLoading ? (
        <div className="flex flex-col items-center justify-center py-20 px-4 rounded-2xl border border-slate-200 dark:border-white/10 text-center">
          <div className="w-8 h-8 border-2 border-cyan-500 border-t-transparent rounded-full animate-spin mb-3"></div>
          <p className="text-xs text-slate-500 dark:text-slate-400">Đang đồng bộ ảnh từ thư mục screen_shot/ trên gương...</p>
        </div>
      ) : photos.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 px-4 rounded-2xl border border-dashed border-slate-300 dark:border-white/10 text-center bg-slate-50/50 dark:bg-white/[0.02]">
          <div className="w-16 h-16 rounded-full bg-violet-500/10 dark:bg-violet-500/20 flex items-center justify-center mb-4">
            <Camera className="w-8 h-8 text-violet-600 dark:text-violet-400" />
          </div>
          <h3 className="text-base font-semibold text-slate-800 dark:text-white mb-1">
            Kho ảnh hiện đang trống
          </h3>
          <p className="text-xs text-slate-500 dark:text-slate-400 max-w-md mb-5 leading-relaxed">
            Thư mục <code className="px-1.5 py-0.5 rounded bg-slate-200 dark:bg-white/10 font-mono text-[11px] text-cyan-600 dark:text-cyan-300">screen_shot/</code> trên gương chưa có bức ảnh nào hoặc bạn vừa xóa hết ảnh. Hãy đứng trước gương và nói: <br />
            <strong className="text-slate-800 dark:text-slate-200">"Chụp cho tôi một bức ảnh"</strong> để lưu lại khoảnh khắc nhé!
          </p>
          {onRefresh && (
            <button
              onClick={onRefresh}
              className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-medium bg-slate-900 text-white hover:bg-slate-800 dark:bg-cyan-500 dark:text-slate-950 dark:hover:bg-cyan-400 cursor-pointer shadow-sm transition-all"
            >
              🔄 Kiểm tra lại thư mục ảnh
            </button>
          )}
        </div>
      ) : filteredPhotos.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 px-4 rounded-2xl border border-dashed border-slate-200 dark:border-white/10 text-center">
          <Camera className="w-12 h-12 text-slate-400 dark:text-slate-600 mb-3" />
          <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-300">
            Không tìm thấy ảnh phù hợp
          </h3>
          <p className="text-xs text-slate-500 mt-1">
            Hãy thử đổi từ khóa tìm kiếm hoặc bấm <strong className="text-cyan-600 dark:text-cyan-400 font-normal">"Tất cả ảnh"</strong>.
          </p>
        </div>
      ) : (
        <div
          className={`grid gap-4 ${
            gridDensity === 'dense'
              ? 'grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5'
              : 'grid-cols-1 sm:grid-cols-2 md:grid-cols-3'
          }`}
        >
          {filteredPhotos.map((photo) => (
            <div
              key={photo.id}
              onClick={() => onSelectPhoto(photo)}
              className="group relative rounded-2xl overflow-hidden border border-slate-200 bg-slate-950 dark:border-white/[0.08] aspect-[4/3] cursor-pointer transition-all duration-200 hover:border-cyan-400/60 hover:shadow-[0_0_20px_rgba(6,182,212,0.25)]"
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
              <div className="absolute top-2.5 left-2.5 right-2.5 flex items-center justify-between pointer-events-none">
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-black/60 backdrop-blur-md text-slate-200 border border-white/10">
                  {photo.tag}
                </span>

                <div className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-cyan-950/85 backdrop-blur-md text-cyan-300 border border-cyan-500/40 opacity-0 group-hover:opacity-100 transition-opacity text-[10px] font-medium shadow-sm">
                  <QrCode className="w-3 h-3 text-cyan-400" />
                  <span>Quét QR tải</span>
                </div>
              </div>

              {/* Bottom Info & Enlarge hint */}
              <div className="absolute bottom-2.5 left-2.5 right-2.5 flex items-end justify-between">
                <div>
                  <span className="text-xs font-semibold text-white block truncate leading-tight">
                    {photo.formattedDate}
                  </span>
                  <span className="text-[10px] text-slate-300 font-mono block mt-0.5">
                    {photo.size}
                  </span>
                </div>

                <div className="w-7 h-7 rounded-lg bg-white/15 backdrop-blur-md flex items-center justify-center text-white opacity-0 group-hover:opacity-100 transition-opacity">
                  <Maximize2 className="w-3.5 h-3.5" />
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

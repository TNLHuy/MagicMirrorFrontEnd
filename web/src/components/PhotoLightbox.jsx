import React, { useEffect, useRef, useState } from 'react'
import QRCode from 'qrcode'
import { X, Download, Share2, ChevronLeft, ChevronRight, Check, Trash2, QrCode as QrIcon } from 'lucide-react'

export default function PhotoLightbox({ photo, onClose, onPrev, onNext, hasPrev, hasNext, onDelete }) {
  const canvasRef = useRef(null)
  const [copied, setCopied] = useState(false)
  const [qrRenderError, setQrRenderError] = useState(false)

  // Construct absolute URL for phone scanning
  const absoluteUrl = typeof window !== 'undefined'
    ? `${window.location.origin}${photo.url}`
    : photo.url

  // Render QR Code onto canvas
  useEffect(() => {
    if (!canvasRef.current) return

    QRCode.toCanvas(
      canvasRef.current,
      absoluteUrl,
      {
        width: 170,
        margin: 1,
        color: {
          dark: '#07090e',
          light: '#ffffff',
        },
      },
      (err) => {
        if (err) {
          console.error('Failed to generate QR code:', err)
          setQrRenderError(true)
        }
      }
    )
  }, [absoluteUrl, photo])

  // Keyboard navigation
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') onClose()
      if (e.key === 'ArrowLeft' && hasPrev) onPrev()
      if (e.key === 'ArrowRight' && hasNext) onNext()
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [onClose, onPrev, onNext, hasPrev, hasNext])

  const handleCopyLink = async () => {
    try {
      await navigator.clipboard.writeText(absoluteUrl)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // Fallback
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6 bg-black/75 dark:bg-black/90 backdrop-blur-md animate-in fade-in duration-200">
      {/* Close button */}
      <button
        onClick={onClose}
        className="absolute top-4 right-4 z-50 p-2.5 rounded-full bg-black/40 hover:bg-black/60 text-white transition-colors cursor-pointer"
        title="Đóng (Esc)"
      >
        <X className="w-5 h-5" />
      </button>

      {/* Prev / Next controls for widescreen */}
      {hasPrev && (
        <button
          onClick={onPrev}
          className="hidden md:flex absolute left-4 top-1/2 -translate-y-1/2 z-50 p-3 rounded-full bg-black/40 hover:bg-black/60 text-white transition-colors cursor-pointer"
          title="Ảnh trước (Mũi tên trái)"
        >
          <ChevronLeft className="w-6 h-6" />
        </button>
      )}
      {hasNext && (
        <button
          onClick={onNext}
          className="hidden md:flex absolute right-4 top-1/2 -translate-y-1/2 z-50 p-3 rounded-full bg-black/40 hover:bg-black/60 text-white transition-colors cursor-pointer"
          title="Ảnh tiếp (Mũi tên phải)"
        >
          <ChevronRight className="w-6 h-6" />
        </button>
      )}

      {/* Content Container */}
      <div className="relative max-w-5xl w-full max-h-[92vh] flex flex-col lg:flex-row rounded-2xl bg-white dark:bg-[#0f121a] border border-slate-200 dark:border-white/10 overflow-hidden shadow-2xl transition-colors">
        {/* Photo View Area */}
        <div className="relative flex-1 bg-black/90 flex items-center justify-center min-h-[280px] sm:min-h-[420px] p-2">
          <img
            src={photo.url}
            alt={photo.fileName}
            className="max-h-[70vh] w-auto max-w-full object-contain rounded-lg"
          />
        </div>

        {/* QR & Details Sidebar */}
        <div className="w-full lg:w-80 p-5 sm:p-6 flex flex-col justify-between border-t lg:border-t-0 lg:border-l border-slate-200 dark:border-white/10 bg-slate-50 dark:bg-[#0c0e15] transition-colors">
          <div className="flex flex-col gap-4">
            <div>
              <span className="text-[11px] font-medium px-2.5 py-0.5 rounded-full bg-cyan-500/10 text-cyan-700 dark:text-cyan-400 border border-cyan-500/30">
                {photo.tag}
              </span>
              <h3 className="text-base font-semibold text-slate-900 dark:text-white mt-2">
                {photo.formattedDate}
              </h3>
              <p className="text-xs text-slate-500 dark:text-slate-400 font-mono mt-0.5 truncate">
                {photo.fileName}
              </p>
            </div>

            {/* QR Code Container */}
            <div className="flex flex-col items-center justify-center p-4 rounded-xl bg-white border border-slate-200 dark:bg-white/[0.03] dark:border-white/[0.08] shadow-sm">
              <div className="p-2 bg-white rounded-lg shadow-sm border border-slate-100 mb-2.5">
                <canvas ref={canvasRef} className="max-w-full h-auto block" />
              </div>
              <div className="flex items-center gap-1.5 text-xs text-cyan-700 dark:text-cyan-300 font-medium">
                <QrIcon className="w-3.5 h-3.5" />
                <span>Quét mã bằng Camera</span>
              </div>
              <p className="text-[11px] text-slate-500 dark:text-slate-400 text-center mt-1 leading-snug">
                Hướng camera điện thoại để mở và tải ảnh này về máy tức thì.
              </p>
            </div>

            {/* Metadata list */}
            <div className="text-xs text-slate-500 dark:text-slate-400 flex flex-col gap-1.5 pt-2 border-t border-slate-200 dark:border-white/[0.06]">
              <div className="flex justify-between">
                <span>Dung lượng ảnh:</span>
                <span className="text-slate-800 dark:text-slate-200 tabular-nums">{photo.size}</span>
              </div>
              <div className="flex justify-between">
                <span>Thư mục lưu:</span>
                <span className="text-slate-700 dark:text-slate-200 font-mono text-[11px]">screen_shot/</span>
              </div>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex flex-col gap-2 pt-4">
            <a
              href={photo.url}
              download={photo.fileName}
              className="flex items-center justify-center gap-2 w-full py-2.5 px-4 rounded-xl bg-cyan-600 hover:bg-cyan-500 text-white dark:bg-cyan-500 dark:hover:bg-cyan-400 dark:text-slate-950 font-semibold text-xs transition-colors shadow-md cursor-pointer"
            >
              <Download className="w-4 h-4" />
              <span>Tải ảnh về máy</span>
            </a>

            <button
              onClick={handleCopyLink}
              className="flex items-center justify-center gap-2 w-full py-2 px-4 rounded-xl bg-slate-200 hover:bg-slate-300 text-slate-800 dark:bg-white/[0.05] dark:hover:bg-white/[0.1] dark:text-slate-200 font-medium text-xs border border-slate-300 dark:border-white/10 transition-colors cursor-pointer"
            >
              {copied ? (
                <>
                  <Check className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
                  <span className="text-emerald-600 dark:text-emerald-400 font-medium">Đã sao chép link!</span>
                </>
              ) : (
                <>
                  <Share2 className="w-3.5 h-3.5" />
                  <span>Sao chép link ảnh</span>
                </>
              )}
            </button>

            {onDelete && (
              <button
                onClick={() => {
                  if (window.confirm(`Bạn có chắc muốn xóa ảnh ${photo.fileName} khỏi gương?`)) {
                    onDelete(photo)
                  }
                }}
                className="flex items-center justify-center gap-1.5 w-full py-2 px-4 rounded-xl text-rose-600 hover:bg-rose-50 dark:text-rose-400 dark:hover:bg-rose-500/10 text-xs font-medium border border-rose-200 dark:border-rose-500/20 transition-colors cursor-pointer mt-1"
              >
                <Trash2 className="w-3.5 h-3.5" />
                <span>Xóa bức ảnh này</span>
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

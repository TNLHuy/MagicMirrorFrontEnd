import React, { useState, useEffect } from 'react'
import Sidebar from './components/Sidebar'
import IotView from './views/IotView'
import CalendarView from './views/CalendarView'
import GalleryView from './views/GalleryView'
import PhotoLightbox from './components/PhotoLightbox'
import { INITIAL_CAPTURES, DEFAULT_CALENDARS } from './data/mockData'

export default function App() {
  const [activeTab, setActiveTab] = useState('iot') // 'iot' | 'calendar' | 'gallery'
  const [theme, setTheme] = useState(() => {
    return localStorage.getItem('magicmirror_theme') || 'dark'
  })

  const [deviceCount, setDeviceCount] = useState(() => {
    try {
      const saved = localStorage.getItem('magicmirror_iot_devices')
      if (saved !== null) {
        const parsed = JSON.parse(saved)
        if (Array.isArray(parsed)) return parsed.length
      }
    } catch {
      // Fallback
    }
    return 0
  })
  const [photos, setPhotos] = useState([])
  const [isLoadingPhotos, setIsLoadingPhotos] = useState(true)
  const [selectedPhotoIndex, setSelectedPhotoIndex] = useState(null)
  const [isPowered, setIsPowered] = useState(true)
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [statusMessage, setStatusMessage] = useState(null)

  // Fetch real photos dynamically from backend/express API
  const fetchPhotos = async () => {
    try {
      setIsLoadingPhotos(true)
      const res = await fetch('/api/photos')
      if (res.ok) {
        const data = await res.json()
        if (Array.isArray(data)) {
          setPhotos(data)
          return
        }
      }
      setPhotos([])
    } catch (err) {
      console.warn('Cannot fetch /api/photos, using empty state:', err)
      setPhotos([])
    } finally {
      setIsLoadingPhotos(false)
    }
  }

  useEffect(() => {
    fetchPhotos()
  }, [])

  // Sync theme with document.documentElement
  useEffect(() => {
    const root = document.documentElement
    if (theme === 'dark') {
      root.classList.add('dark')
    } else {
      root.classList.remove('dark')
    }
    localStorage.setItem('magicmirror_theme', theme)
  }, [theme])

  const handleToggleTheme = () => {
    setTheme((prev) => (prev === 'dark' ? 'light' : 'dark'))
  }

  const handleRefresh = async () => {
    setIsRefreshing(true)
    setStatusMessage('Đang đồng bộ dữ liệu với gương MagicMirror & thư viện ảnh...')
    await fetchPhotos()
    setIsRefreshing(false)
    setStatusMessage('Đã đồng bộ toàn bộ dữ liệu thực tế từ thư mục ảnh.')
    setTimeout(() => setStatusMessage(null), 3000)
  }

  const handleDeletePhoto = async (photo) => {
    try {
      const res = await fetch(`/api/photos/${photo.fileName}`, { method: 'DELETE' })
      if (res.ok) {
        setPhotos((prev) => prev.filter((p) => p.id !== photo.id))
        setSelectedPhotoIndex(null)
        setStatusMessage(`Đã xóa ảnh ${photo.fileName} thành công.`)
        setTimeout(() => setStatusMessage(null), 3000)
      }
    } catch (err) {
      console.error('Lỗi khi xóa ảnh:', err)
    }
  }

  const handleSelectPhoto = (photo) => {
    const idx = photos.findIndex((p) => p.id === photo.id)
    if (idx !== -1) setSelectedPhotoIndex(idx)
  }

  const handlePrevPhoto = () => {
    if (selectedPhotoIndex > 0) {
      setSelectedPhotoIndex(selectedPhotoIndex - 1)
    }
  }

  const handleNextPhoto = () => {
    if (selectedPhotoIndex < photos.length - 1) {
      setSelectedPhotoIndex(selectedPhotoIndex + 1)
    }
  }

  const currentPhoto = selectedPhotoIndex !== null ? photos[selectedPhotoIndex] : null

  return (
    <div className="min-h-screen bg-slate-100 text-slate-900 dark:bg-[#07090e] dark:text-slate-100 flex flex-col lg:flex-row antialiased transition-colors duration-150">
      {/* Left Sidebar (Desktop) & Top Header + Bottom Bar (Mobile) */}
      <Sidebar
        activeTab={activeTab}
        onTabChange={setActiveTab}
        theme={theme}
        onToggleTheme={handleToggleTheme}
        onRefresh={handleRefresh}
        isRefreshing={isRefreshing}
        photoCount={photos.length}
        calendarCount={DEFAULT_CALENDARS.length}
        deviceCount={deviceCount}
      />

      {/* Main Dynamic Workspace Area */}
      <div className="flex-1 flex flex-col min-w-0 pb-20 lg:pb-8">
        {/* Sync Status Banner */}
        {statusMessage && (
          <div className="bg-cyan-50 border-b border-cyan-200 text-cyan-800 dark:bg-cyan-950/60 dark:border-cyan-500/30 dark:text-cyan-300 px-4 py-2 text-center text-xs font-medium animate-in fade-in transition-colors">
            {statusMessage}
          </div>
        )}

        {/* Dynamic Tab View Container */}
        <main className="flex-1 p-4 sm:p-6 lg:p-8">
          {activeTab === 'iot' && (
            <IotView
              isPowered={isPowered}
              setIsPowered={setIsPowered}
              onDeviceCountChange={setDeviceCount}
              onStateChange={(state) => {
                console.log('ESP32 State updated:', state)
              }}
            />
          )}

          {activeTab === 'calendar' && <CalendarView />}

          {activeTab === 'gallery' && (
            <GalleryView
              photos={photos}
              onSelectPhoto={handleSelectPhoto}
              onRefresh={fetchPhotos}
              isLoading={isLoadingPhotos}
            />
          )}
        </main>
      </div>

      {/* Lightbox Modal with dynamic QR Code */}
      {currentPhoto && (
        <PhotoLightbox
          photo={currentPhoto}
          onClose={() => setSelectedPhotoIndex(null)}
          onPrev={handlePrevPhoto}
          onNext={handleNextPhoto}
          hasPrev={selectedPhotoIndex > 0}
          hasNext={selectedPhotoIndex < photos.length - 1}
          onDelete={handleDeletePhoto}
        />
      )}
    </div>
  )
}

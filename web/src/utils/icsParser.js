/**
 * Minimal RFC 5545 iCalendar (.ics) Parser for browser execution
 */

export function parseICS(icsData, calendarInfo = {}) {
  if (!icsData || typeof icsData !== 'string') return []

  const events = []
  const lines = icsData.replace(/\r\n/g, '\n').replace(/\n /g, '').split('\n')
  let currentEvent = null

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim()
    if (!line) continue

    if (line === 'BEGIN:VEVENT') {
      currentEvent = {}
      continue
    }

    if (line === 'END:VEVENT') {
      if (currentEvent && currentEvent.title) {
        events.push({
          ...currentEvent,
          id: currentEvent.uid || `evt_${Math.random().toString(36).substring(2, 9)}`,
          calendarId: calendarInfo.id || 'default',
          calendarName: calendarInfo.name || 'Lịch Google',
          color: calendarInfo.color || '#06b6d4',
        })
      }
      currentEvent = null
      continue
    }

    if (!currentEvent) continue

    const colonIdx = line.indexOf(':')
    if (colonIdx === -1) continue

    const keyPart = line.substring(0, colonIdx)
    const value = line.substring(colonIdx + 1)
    const [key, ...params] = keyPart.split(';')

    switch (key) {
      case 'UID':
        currentEvent.uid = value
        break
      case 'SUMMARY':
        currentEvent.title = unescapeICS(value)
        break
      case 'DESCRIPTION':
        currentEvent.description = unescapeICS(value)
        break
      case 'LOCATION':
        currentEvent.location = unescapeICS(value)
        break
      case 'DTSTART':
        currentEvent.start = parseICSDate(value, params)
        currentEvent.isAllDay = value.length === 8 // YYYYMMDD
        break
      case 'DTEND':
        currentEvent.end = parseICSDate(value, params)
        break
      case 'STATUS':
        currentEvent.status = value
        break
      default:
        break
    }
  }

  return events.sort((a, b) => (a.start?.getTime() || 0) - (b.start?.getTime() || 0))
}

function unescapeICS(str) {
  if (!str) return ''
  return str
    .replace(/\\n/g, '\n')
    .replace(/\\,/g, ',')
    .replace(/\\;/g, ';')
    .replace(/\\\\/g, '\\')
}

function parseICSDate(val, params) {
  if (!val) return null

  // Clean value (e.g. YYYYMMDD or YYYYMMDDTHHMMSSZ)
  const clean = val.replace(/[^0-9TZ]/g, '')

  if (clean.length === 8) {
    // All day: YYYYMMDD
    const year = parseInt(clean.substring(0, 4), 10)
    const month = parseInt(clean.substring(4, 6), 10) - 1
    const day = parseInt(clean.substring(6, 8), 10)
    return new Date(year, month, day, 0, 0, 0)
  }

  if (clean.length >= 15) {
    // YYYYMMDDTHHMMSS(Z)
    const year = parseInt(clean.substring(0, 4), 10)
    const month = parseInt(clean.substring(4, 6), 10) - 1
    const day = parseInt(clean.substring(6, 8), 10)
    const hour = parseInt(clean.substring(9, 11), 10)
    const minute = parseInt(clean.substring(11, 13), 10)
    const second = parseInt(clean.substring(13, 15), 10)

    if (clean.endsWith('Z')) {
      return new Date(Date.UTC(year, month, day, hour, minute, second))
    }
    return new Date(year, month, day, hour, minute, second)
  }

  return new Date(val)
}

/**
 * Format relative time indicator (e.g. "Hôm nay 14:00", "Còn 45 phút", "Ngày mai", "Cả ngày")
 */
export function formatEventTiming(date, isAllDay = false) {
  if (!date) return ''
  const now = new Date()
  const isToday =
    date.getDate() === now.getDate() &&
    date.getMonth() === now.getMonth() &&
    date.getFullYear() === now.getFullYear()

  const tomorrow = new Date(now)
  tomorrow.setDate(tomorrow.getDate() + 1)
  const isTomorrow =
    date.getDate() === tomorrow.getDate() &&
    date.getMonth() === tomorrow.getMonth() &&
    date.getFullYear() === tomorrow.getFullYear()

  const timeString = isAllDay
    ? 'Cả ngày'
    : date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false })

  if (isToday) {
    const diffMs = date.getTime() - now.getTime()
    if (!isAllDay && diffMs > 0 && diffMs < 3600000) {
      const mins = Math.round(diffMs / 60000)
      return `Còn ${mins}p`
    }
    return `Hôm nay ${timeString}`
  }

  if (isTomorrow) {
    return `Ngày mai ${timeString}`
  }

  const dateStr = date.toLocaleDateString('vi-VN', { weekday: 'short', day: 'numeric', month: 'numeric' })
  return `${dateStr} · ${timeString}`
}

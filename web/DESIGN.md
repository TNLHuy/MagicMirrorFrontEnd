---
name: Web_MagicMirror
description: Adaptive Dual-Theme (Dark Obsidian & Crisp Light) companion IoT dashboard and photo gallery for physical MagicMirror2
colors:
  dark-bg-ground: "#07090e"
  dark-surface-card: "#0d1017"
  dark-surface-hover: "#161b26"
  light-bg-ground: "#f8fafc"
  light-surface-card: "#ffffff"
  light-surface-hover: "#f1f5f9"
  cyan-primary: "#06b6d4"
  cyan-dark: "#0891b2"
  violet-accent: "#8b5cf6"
  emerald-status: "#10b981"
  amber-warning: "#f59e0b"
  blue-accent: "#3b82f6"
  rose-accent: "#ec4899"
  text-primary: "#f8fafc"
  text-secondary: "#94a3b8"
  text-light-primary: "#0f172a"
  text-light-secondary: "#475569"
  border-subtle: "rgba(255, 255, 255, 0.08)"
  border-light: "rgba(0, 0, 0, 0.08)"
typography:
  fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
  monoFontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace'
rounded:
  sm: "6px"
  md: "8px"
  lg: "12px"
  xl: "16px"
  full: "9999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "24px"
  xl: "32px"
components:
  card:
    backgroundColor: "{colors.dark-surface-card}"
    textColor: "{colors.text-primary}"
    rounded: "{rounded.xl}"
    padding: "24px"
  button-primary:
    backgroundColor: "{colors.cyan-primary}"
    textColor: "#07090e"
    rounded: "{rounded.lg}"
    padding: "10px 16px"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.text-secondary}"
    rounded: "{rounded.md}"
    padding: "6px 12px"
---

# Design System: Web_MagicMirror

## Overview

Web_MagicMirror is an adaptive dual-theme companion web hub that extends the physical MagicMirror2 smart mirror experience to mobile phones, tablets, and desktop browsers. It supports both **Ambient Dark Mode** (obsidian tones `#07090e` for dim evening home lighting) and **Crisp Light Mode** (`#f8fafc` background with pure white cards `#ffffff` for daylight/well-lit environments).

## Colors

- **Dark Mode (Default Mirror Companion):**
  - Ground: Deep Obsidian (`#07090e`) for OLED blacks and authentic mirror ambience.
  - Surface cards: Obsidian Slate (`#0d1017`) at 90% opacity with backdrop blur.
  - Borders: Hairline translucent borders (`rgba(255, 255, 255, 0.08)`).
  - Text: Primary `#f8fafc`, Secondary `#94a3b8`, Muted `#64748b`.
- **Light Mode:**
  - Ground: Clean Soft Slate (`#f8fafc` / `#f1f5f9`).
  - Surface cards: Crisp White (`#ffffff`) with subtle 1px border (`#e2e8f0`) and soft elevation shadow.
  - Text: Primary Dark Slate (`#0f172a`, WCAG AAA > 12:1), Secondary `#475569`, Muted `#64748b`.
- **Universal Interactive Accents:**
  - **Cyan / Teal (`#06b6d4` / `#0891b2`):** Primary branding, matching the circular Gemini AI orb on the mirror.
  - **Violet (`#8b5cf6` / `#7c3aed`):** Snapshot gallery tags and timestamps.
  - **Emerald (`#10b981` / `#059669`):** Real-time online telemetry and confirmed hardware states.
  - **Amber (`#f59e0b` / `#d97706`):** Warm lighting scenes and alerts.

## Typography

- **System UI Stack:** `-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif` ensures instantaneous rendering with zero layout shift across devices.
- **Mono Numerics:** `font-variant-numeric: tabular-nums` across all timestamps, percentages, IP addresses, and countdown timers for stable alignment.
- **Hierarchy:**
  - Heading 1: `1.125rem` (`18px`), font-semibold, letter-spacing -0.015em.
  - Heading 2: `1rem` (`16px`), font-semibold, letter-spacing -0.01em.
  - Body: `0.875rem` (`14px`), line-height 1.5.
  - Secondary / Captions: `0.75rem` (`12px`) and `0.6875rem` (`11px`).

## Layout

- **Desktop App-Shell with Left Sidebar (≥ 1024px):** Fixed left navigation bar (`w-72`) displaying brand status, section links with count badges, and system controls. The right area provides a spacious, uncluttered workspace for the active view.
- **Mobile Responsive Navigation (< 1024px):** Sticky top bar with quick actions + floating bottom navigation bar for effortless thumb reach across the 3 sections (`Thiết bị IoT`, `Lịch trình`, `Kho ảnh`).

## Elevation & Depth

- Hairline 1px borders define boundaries without visual clutter (`rgba(255, 255, 255, 0.08)` in dark mode, `#e2e8f0` in light mode).
- Glowing accents utilize subtle spread and blur (`shadow-[0_0_15px_rgba(6,182,212,0.15)]`), rejecting harsh 0-blur offset shadows.
- Modal backdrops apply responsive dark tint with backdrop blur for clear focus.

## Shapes

- Cards: Rounded 16px (`rounded-2xl`).
- Controls, Pills, and Tags: Rounded 8px to 12px (`rounded-lg` / `rounded-xl`).
- Badges and Toggles: Pill shape (`rounded-full`).

## Components

- **Left Navigation Sidebar:** Displays brand header, 3 dedicated section links (`Thiết bị IoT`, `Lịch trình`, `Kho ảnh`) with count badges, theme toggle, and live physical mirror connection telemetry.
- **IoT & Smart Home View:** ESP32 mirror LED strip controls (power, 4 atmosphere scenes, brightness slider, custom colors, mode selector) + connected household smart home appliances (lights, air conditioner, ventilation fan, smart speaker).
- **Google Calendar View:** Dedicated multi-feed schedule timeline with quick calendar filter chips (`Bật/Tắt từng nguồn lịch`), sync status, and `.ics` URL manager modal.
- **Photo Gallery View:** Dedicated photo archive with tag filters, search input, grid density selector, and full-resolution QR Code Lightbox for instant mobile downloads.

## Do's and Don'ts

### Do's
- Always maintain high contrast (≥4.5:1) for all body text in both Light and Dark modes.
- Use `tabular-nums` for timers, clock digits, and percentage indicators.
- Provide immediate visual confirmation (e.g. glowing pulses, checkmarks) when IoT states change.
- Ensure QR codes are drawn with high contrast (`#07090e` on white) for fast camera detection in all lighting conditions.

### Don'ts
- Do not use colored kickers or eyebrows above section headings.
- Do not use 0-blur block shadows.
- Do not use gradient text.
- Do not obscure hardware error states with ambiguous loading spinners.

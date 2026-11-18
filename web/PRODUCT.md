# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

React + Vite + Tailwind CSS

## Users

Owners and household users of the physical MagicMirror smart mirror assistant who interact with the system at home, checking status or retrieving captured photos on their mobile phones, tablets, or desktop browsers.

## Product Purpose

Serve as the companion IoT dashboard and gallery web application for the MagicMirror ecosystem. It monitors and controls ESP32 IoT LED device statuses, displays photos taken by the smart mirror's camera with instant QR codes for mobile downloads, and synchronizes personal Google Calendar schedules. Success means seamless glanceability, rapid photo retrieval, and reliable hardware device control from any screen in the home.

## Positioning

The dedicated companion web hub for the custom MagicMirror2 + ESP32 AI assistant, directly bridging physical mirror interactions (webcam snapshots, smart home lighting, daily schedules) with personal handheld devices.

## Operating Context

- Home network environment (mobile browsers, tablets, and desktop computers).
- Operates in tandem with the physical MagicMirror (`MagicMirror-master`) running Python backend controllers, circular orb Gemini AI, and local snapshot storage (`screen_shot/`).
- Interacts with ESP32 microcontrollers for ambient/task LED lighting and Google Calendar integration.

## Capabilities and Constraints

- **Capabilities:**
  - **ESP32 IoT LED Monitoring & Control:** Monitor connection status, power, color, and mode of ESP32-powered LEDs.
  - **Smart Mirror Photo Gallery:** Browse captures taken via the mirror's `TAKE_PHOTO` action, with QR codes generated for quick mobile download and sharing.
  - **Schedule & Multi-Calendar Sync:** Add, manage, and toggle multiple Google Calendar private iCal (.ics) links simultaneously with custom labels, color coding, visibility filters, and direct synchronization to the physical MagicMirror2 screen and companion web dashboard.
- **Constraints:**
  - Modern web application architecture using React + Vite + Tailwind CSS.
  - Interoperable with local MagicMirror data paths and network endpoints.

## Brand Commitments

Dark-mode ambient aesthetic resonant with smart mirror hardware (sleek glass, subtle glows, high-contrast typography, and refined modern surfaces).

## Evidence on Hand

- Sibling repository at `D:\magicMirror\MagicMirror-master` containing system architecture, 10-action NLU documentation (`huongdan.md`), snapshot storage folder (`screen_shot/`), and backend controller configurations.

## Product Principles

1. **Companion Harmony:** Complement the physical mirror's glanceable display by handling detailed inspection, gallery downloads, and device controls on personal screens.
2. **Instant Utility:** Access photos via QR codes and check LED/calendar states in minimal taps with zero cognitive friction.
3. **Hardware Truth:** Display clear, accurate live status for ESP32 and mirror connectivity; avoid misleading mock states.
4. **Refined Ambient Craft:** Deliver an interface whose dark-mode palette, typography, and motion feel like an organic extension of the physical mirror's glass surface.

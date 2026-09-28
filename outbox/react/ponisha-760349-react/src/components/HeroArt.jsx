import React from 'react'

/** تصویر جایگزینِ داخلی (SVG) — بدون نیاز به اینترنت */
export default function HeroArt() {
  return (
    <svg viewBox="0 0 520 360" className="w-full h-auto" role="img" aria-label="طرح صفحه اصلی">
      <defs>
        <linearGradient id="hg" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#ffffff" stopOpacity="0.3" />
          <stop offset="1" stopColor="#ffffff" stopOpacity="0" />
        </linearGradient>
      </defs>
      <rect x="10" y="14" width="500" height="330" rx="22" fill="url(#hg)" />
      <rect x="48" y="52" width="424" height="150" rx="16" fill="#ffffff" opacity="0.92" />
      <rect x="70" y="76" width="120" height="12" rx="6" fill="#ffffff" opacity="0.55" />
      <rect x="70" y="100" width="220" height="10" rx="5" fill="#c7d0e6" />
      <rect x="70" y="122" width="170" height="10" rx="5" fill="#dbe1ee" />
      <rect x="330" y="86" width="112" height="82" rx="12" fill="#ffffff" opacity="0.35" />
      {[0, 1, 2].map((i) => (
        <rect key={i} x={48 + i * 143} y="222" width="130" height="104" rx="14"
              fill="#ffffff" opacity={0.9 - i * 0.15} />
      ))}
    </svg>
  )
}

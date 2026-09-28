import React from 'react'
import content from '../content.js'

export default function Cta() {
  return (
    <section className="py-12">
      <div className="mx-auto max-w-6xl px-4">
        <div className="rounded-3xl bg-hero px-6 py-12 text-center text-white">
          <h2 className="text-2xl font-heading font-bold">آماده‌ی شروع هستید؟</h2>
          <p className="mx-auto mt-2 max-w-xl text-sm text-white/90">
            {content.tagline} — همین امروز پیام بدهید تا زمان‌بندی قطعی شود.
          </p>
          <button className="mt-6 rounded-xl bg-white px-7 py-3 text-sm font-bold text-ink">
            {content.cta1}
          </button>
        </div>
      </div>
    </section>
  )
}

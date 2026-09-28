import React from 'react'
import content from '../content.js'

export default function Footer() {
  return (
    <footer className="bg-ink/95 py-10 text-sm text-white/70">
      <div className="mx-auto max-w-6xl px-4 grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
        <div>
          <h4 className="mb-2 font-bold text-white">{content.brand}</h4>
          <p>{content.tagline}</p>
        </div>
        <div>
          <h4 className="mb-2 font-bold text-white">دسترسی سریع</h4>
          {content.nav.map((n) => <div key={n}>{n}</div>)}
        </div>
        <div>
          <h4 className="mb-2 font-bold text-white">خدمات</h4>
          {content.services.slice(0, 4).map((s) => <div key={s.title}>{s.title}</div>)}
        </div>
        <div>
          <h4 className="mb-2 font-bold text-white">تماس</h4>
          <div>info@example.com</div>
          <div>۰۲۱-۱۲۳۴۵۶۷۸</div>
        </div>
      </div>
      <div className="mt-8 border-t border-white/10 pt-4 text-center text-xs">
        تولیدشده با فریلنس‌یار آرنا — کد واقعی پروژه، آماده‌ی توسعه
      </div>
    </footer>
  )
}

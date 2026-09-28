import React, { useState } from 'react'

const ROWS = [
  ['چه مدت طول می‌کشد؟', 'زمان تحویل دقیق در پیشنهاد ارسالی نوشته شده است.'],
  ['امکان تغییر بعد از تحویل دارم؟', 'بله؛ یک دور بازنگری رایگان پس از تحویل در نظر گرفته می‌شود.'],
  ['روی موبایل هم درست کار می‌کند؟', 'بله؛ طراحی کاملاً واکنش‌گرا است و روی موبایل تست می‌شود.'],
  ['پشتیبانی بعد از تحویل چطور است؟', 'رفع اشکال و آموزش کار با پنل پس از تحویل ارائه می‌شود.'],
]

export default function Faq() {
  const [open, setOpen] = useState(0)
  return (
    <section className="mx-auto max-w-3xl px-4 py-14">
      <h2 className="text-center text-2xl font-heading font-bold">سؤالات متداول</h2>
      <div className="mt-8 space-y-3">
        {ROWS.map(([q, a], i) => (
          <div key={q} className="bg-surface border border-line shadow-card rounded-card">
            <button
              onClick={() => setOpen(open === i ? -1 : i)}
              className="flex w-full items-center justify-between gap-4 p-4 text-right"
              aria-expanded={open === i}
            >
              <span className="font-semibold text-[15px]">❓ {q}</span>
              <span className="text-primary text-xl">{open === i ? '−' : '+'}</span>
            </button>
            {open === i && <p className="px-4 pb-4 text-sm text-muted leading-7">{a}</p>}
          </div>
        ))}
      </div>
    </section>
  )
}

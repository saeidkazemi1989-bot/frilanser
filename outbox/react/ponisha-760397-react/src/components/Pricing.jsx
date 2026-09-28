import React from 'react'
import content from '../content.js'

const PLANS = [
  { name: 'پایه', tag: 'برای شروع', desc: 'صفحه‌ی اصلی + فرم تماس' },
  { name: 'حرفه‌ای', tag: 'پرفروش‌ترین', desc: 'چند صفحه + پنل مدیریت' },
  { name: 'سازمانی', tag: 'برای رشد', desc: 'صفحات بیشتر + سئو' },
]

export default function Pricing() {
  return (
    <section className="mx-auto max-w-6xl px-4 py-14">
      <h2 className="text-center text-2xl font-heading font-bold">بسته‌های پیشنهادی {content.brand}</h2>
      <p className="mt-2 text-center text-sm text-muted">
        قیمت نهایی همان مبلغی است که در پیشنهاد ارسالی می‌بینید
      </p>
      <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {PLANS.map((p) => (
          <div key={p.name} className="bg-surface border border-line shadow-card rounded-card p-6 text-center">
            <div className="text-xs text-muted">{p.tag}</div>
            <h3 className="mt-1 text-lg font-bold">{p.name}</h3>
            <div className="mt-2 text-xl font-extrabold text-primary">توافقی</div>
            <p className="mt-2 text-sm text-muted">{p.desc}</p>
            <button className="mt-4 rounded-xl border border-primary px-5 py-2 text-sm text-primary">
              انتخاب بسته
            </button>
          </div>
        ))}
      </div>
    </section>
  )
}

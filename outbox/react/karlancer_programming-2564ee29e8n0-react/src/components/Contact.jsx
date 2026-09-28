import React, { useState } from 'react'

export default function Contact() {
  const [sent, setSent] = useState(false)
  return (
    <section className="mx-auto max-w-6xl px-4 py-14">
      <h2 className="text-center text-2xl font-heading font-bold">تماس با ما</h2>
      <div className="mt-8 grid gap-6 md:grid-cols-[1.2fr_.8fr]">
        <form
          onSubmit={(e) => { e.preventDefault(); setSent(true) }}
          className="bg-surface border border-line shadow-card rounded-card p-5"
        >
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="text-sm">
              <span className="mb-1 block text-muted">نام و نام خانوادگی</span>
              <input className="w-full rounded-xl border border-line bg-white/70 px-3 py-2 text-sm"
                     placeholder="مثال: علی محمدی" />
            </label>
            <label className="text-sm">
              <span className="mb-1 block text-muted">شماره تماس</span>
              <input className="w-full rounded-xl border border-line bg-white/70 px-3 py-2 text-sm"
                     placeholder="09xxxxxxxxx" />
            </label>
          </div>
          <label className="mt-3 block text-sm">
            <span className="mb-1 block text-muted">توضیحات</span>
            <textarea rows="4" className="w-full rounded-xl border border-line bg-white/70 px-3 py-2 text-sm"
                      placeholder="متن پیام شما…" />
          </label>
          <button className="mt-4 rounded-xl bg-primary px-6 py-2.5 text-sm text-white">
            ارسال درخواست
          </button>
          {sent && <p className="mt-3 text-sm text-emerald-600">درخواست شما ثبت شد (نمونه).</p>}
        </form>
        <div className="space-y-3 text-sm">
          {[['📞 تلفن', '۰۲۱-۱۲۳۴۵۶۷۸'], ['✉️ ایمیل', 'info@example.com'],
            ['📍 آدرس', 'تهران، خیابان نمونه، پلاک ۱۲'], ['🕘 ساعات کاری', 'شنبه تا چهارشنبه ۹ تا ۱۸']]
            .map(([k, v]) => (
              <div key={k} className="bg-surface border border-line shadow-card rounded-card p-4">
                <div className="font-semibold">{k}</div>
                <div className="text-muted">{v}</div>
              </div>
            ))}
        </div>
      </div>
    </section>
  )
}

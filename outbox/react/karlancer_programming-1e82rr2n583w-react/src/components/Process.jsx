import React from 'react'

const STEPS = ['نیازسنجی و جمع‌آوری نیازها', 'تایید طرح گرافیکی', 'اجرا و بارگذاری محتوا',
  'آموزش، تست و تحویل']

export default function Process() {
  return (
    <section className="bg-black/[.03] py-14">
      <div className="mx-auto max-w-6xl px-4">
        <h2 className="text-center text-2xl font-heading font-bold">مسیر همکاری</h2>
        <p className="mt-2 text-center text-sm text-muted">از امروز تا تحویل</p>
        <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {STEPS.map((t, i) => (
            <div key={t} className="bg-surface border border-line shadow-card rounded-card p-5 text-center">
              <div className="mx-auto mb-2 grid h-9 w-9 place-items-center rounded-full bg-primary text-white text-sm">
                {i + 1}
              </div>
              <div className="font-semibold text-sm">{t}</div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

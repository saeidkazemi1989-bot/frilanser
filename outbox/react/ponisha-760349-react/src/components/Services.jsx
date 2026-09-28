import React from 'react'
import content from '../content.js'

export default function Services() {
  return (
    <section className="mx-auto max-w-6xl px-4 py-14">
      <h2 className="text-center text-2xl font-heading font-bold">امکاناتی که پیاده‌سازی می‌شود</h2>
      <p className="mt-2 text-center text-sm text-muted">
        هر بخش در نسخه‌ی نهایی به‌طور کامل و قابل استفاده تحویل می‌گردد
      </p>
      <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {content.services.map((s) => (
          <article key={s.title} className="bg-surface border border-line shadow-card rounded-card p-5">
            <div className="mb-3 grid h-11 w-11 place-items-center rounded-xl bg-black/5 text-xl">
              {s.icon}
            </div>
            <h3 className="font-bold">{s.title}</h3>
            <p className="mt-1 text-sm text-muted leading-7">{s.desc}</p>
          </article>
        ))}
      </div>
    </section>
  )
}

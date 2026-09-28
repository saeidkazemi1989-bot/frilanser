import React from 'react'
import content from '../content.js'

const items = []
for (let i = 0; i < content.testimonials.length; i += 2) {
  items.push({ text: content.testimonials[i], who: content.testimonials[i + 1] || '' })
}

export default function Testimonials() {
  return (
    <section className="bg-black/[.03] py-14">
      <div className="mx-auto max-w-6xl px-4">
        <h2 className="text-center text-2xl font-heading font-bold">نظر کاربران</h2>
        <div className="mt-8 grid gap-4 sm:grid-cols-2">
          {items.map((t) => (
            <figure key={t.text} className="bg-surface border border-line shadow-card rounded-card p-5">
              <blockquote className="text-sm text-muted leading-7">«{t.text}»</blockquote>
              <figcaption className="mt-4 flex items-center gap-3">
                <span className="h-9 w-9 rounded-full bg-hero" />
                <span className="text-sm font-semibold">{t.who}</span>
              </figcaption>
            </figure>
          ))}
        </div>
      </div>
    </section>
  )
}

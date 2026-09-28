import React from 'react'
import content from '../content.js'

export default function Products() {
  if (!content.products || content.products.length === 0) return null
  return (
    <section className="mx-auto max-w-6xl px-4 py-14">
      <h2 className="text-center text-2xl font-heading font-bold">نمونه محصولات</h2>
      <p className="mt-2 text-center text-sm text-muted">کارت محصول با تصویر، قیمت و دکمه‌ی خرید</p>
      <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {content.products.map((p) => (
          <article key={p.name} className="bg-surface border border-line shadow-card overflow-hidden rounded-card">
            <div className="h-36 grid place-items-center text-4xl" style={{ background: p.color }}>
              🛍️
            </div>
            <div className="p-4">
              <h3 className="font-semibold text-[15px]">{p.name}</h3>
              <div className="mt-2 flex items-center gap-2">
                {p.old && <span className="text-xs text-muted line-through">{p.old}</span>}
                <span className="font-extrabold text-emerald-700">{p.price}</span>
                <span className="text-[11px] font-normal">تومان</span>
              </div>
            </div>
          </article>
        ))}
      </div>
    </section>
  )
}

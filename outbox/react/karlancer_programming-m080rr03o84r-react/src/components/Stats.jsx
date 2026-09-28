import React from 'react'
import content from '../content.js'

export default function Stats() {
  return (
    <section className="bg-black/[.03] py-12">
      <div className="mx-auto max-w-6xl px-4 grid gap-6 text-center sm:grid-cols-2 lg:grid-cols-4">
        {content.stats.map((s) => (
          <div key={s.k}>
            <div className="text-3xl font-heading font-extrabold text-primary">{s.v}</div>
            <div className="mt-1 text-sm text-muted">{s.k}</div>
          </div>
        ))}
      </div>
    </section>
  )
}

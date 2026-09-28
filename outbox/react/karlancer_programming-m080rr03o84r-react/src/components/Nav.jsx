import React, { useState } from 'react'
import content from '../content.js'

export default function Nav() {
  const [open, setOpen] = useState(false)
  return (
    <header className="sticky top-0 z-40 bg-surface border-b border-line">
      <div className="mx-auto max-w-6xl px-4 py-3 flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <span className="grid h-9 w-9 place-items-center rounded-xl bg-hero text-white font-heading text-lg">
            {content.brand.charAt(0)}
          </span>
          <span className="font-heading font-bold text-lg">{content.brand}</span>
        </div>
        <nav className="hidden md:flex items-center gap-6 text-sm text-muted">
          {content.nav.map((item) => (
            <a key={item} href="#" className="hover:text-primary transition-colors">{item}</a>
          ))}
        </nav>
        <button className="hidden md:inline-flex rounded-xl bg-primary px-5 py-2 text-white text-sm font-medium">
          {content.cta1}
        </button>
        <button
          onClick={() => setOpen((v) => !v)}
          className="md:hidden rounded-lg border border-line px-3 py-2 text-sm"
          aria-expanded={open}
          aria-label="منو"
        >
          ☰
        </button>
      </div>
      {open && (
        <nav className="md:hidden border-t border-line px-4 py-3 flex flex-col gap-3 text-sm">
          {content.nav.map((item) => (
            <a key={item} href="#" className="text-muted">{item}</a>
          ))}
        </nav>
      )}
    </header>
  )
}

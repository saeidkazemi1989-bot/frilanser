import React from 'react'
import content from '../content.js'
import HeroArt from './HeroArt.jsx'

export default function Hero() {
  return (
    <section className="bg-hero text-white">
      <div className="mx-auto max-w-6xl px-4 py-16 grid gap-10 md:grid-cols-2 items-center">
        <div>
          <span className="inline-block rounded-full bg-white/20 px-4 py-1 text-xs backdrop-blur">
            {content.tagline}
          </span>
          <h1 className="mt-4 text-3xl md:text-4xl font-heading font-bold leading-snug">
            {content.hero_t}
          </h1>
          <p className="mt-4 text-white/90 leading-8 text-[15px]">{content.hero_d}</p>
          <div className="mt-7 flex flex-wrap gap-3">
            <button className="rounded-xl bg-white px-6 py-3 text-sm font-bold text-ink">
              {content.cta1}
            </button>
            <button className="rounded-xl border border-white/50 px-6 py-3 text-sm">
              {content.cta2}
            </button>
          </div>
          <div className="mt-6 flex flex-wrap gap-3 text-xs text-white/80">
            <span>✓ واکنش‌گرا</span><span>✓ سریع</span><span>✓ سئو پایه</span>
          </div>
        </div>
        <HeroArt />
      </div>
    </section>
  )
}

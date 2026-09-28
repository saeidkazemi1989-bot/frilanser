import React from 'react'
import content from './content.js'
import Nav from './components/Nav.jsx'
import Hero from './components/Hero.jsx'
import Services from './components/Services.jsx'
import Stats from './components/Stats.jsx'
import Products from './components/Products.jsx'
import Process from './components/Process.jsx'
import Pricing from './components/Pricing.jsx'
import Testimonials from './components/Testimonials.jsx'
import Faq from './components/Faq.jsx'
import Contact from './components/Contact.jsx'
import Cta from './components/Cta.jsx'
import Footer from './components/Footer.jsx'

export default function App() {
  return (
    <div className="min-h-screen bg-bg text-ink font-body">
      <Nav />
      <main>
        <Hero />
        <Services />
        <Stats />
        <Products />
        <Process />
        <Pricing />
        <Testimonials />
        <Faq />
        <Contact />
        <Cta />
      </main>
      <Footer />
    </div>
  )
}

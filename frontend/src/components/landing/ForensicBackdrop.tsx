import { useEffect, useState } from 'react'

/**
 * Lightweight, CSS/SVG-only forensic backdrop for the landing hero.
 * No WebGL, no particle systems — just a faint data-field grid, four
 * evidence-frame corner brackets (camera-viewfinder read), a slow scan
 * sweep, film-sprocket edge markers (a literal nod to "24FPS"), and a
 * ticking frame counter. Everything is decorative and pointer-events: none,
 * and the sweep animation is skipped when the user prefers reduced motion.
 */

function SprocketColumn({ side }: { side: 'left' | 'right' }) {
  return (
    <div
      className={`absolute top-0 h-full w-6 ${side === 'left' ? 'left-0' : 'right-0'} flex flex-col items-center justify-evenly py-8 opacity-20`}
      aria-hidden
    >
      {Array.from({ length: 14 }).map((_, i) => (
        <span key={i} className="h-2.5 w-2.5 rounded-[2px] border border-white/70" />
      ))}
    </div>
  )
}

function CornerBracket({ position }: { position: 'tl' | 'tr' | 'bl' | 'br' }) {
  const pos = {
    tl: 'top-8 left-8 border-l border-t',
    tr: 'top-8 right-8 border-r border-t',
    bl: 'bottom-8 left-8 border-l border-b',
    br: 'bottom-8 right-8 border-r border-b',
  }[position]
  return <div className={`absolute h-10 w-10 border-white/25 ${pos}`} aria-hidden />
}

export function ForensicBackdrop() {
  const [frame, setFrame] = useState(184213)
  const [reducedMotion, setReducedMotion] = useState(false)

  useEffect(() => {
    setReducedMotion(window.matchMedia('(prefers-reduced-motion: reduce)').matches)
    const interval = setInterval(() => setFrame((f) => f + 24), 1000)
    return () => clearInterval(interval)
  }, [])

  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden">
      <div className="absolute inset-0 bg-forensic-grid-light opacity-40" />
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_80%_60%_at_50%_0%,rgba(0,0,0,0.25),transparent_60%)]" />
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_70%_50%_at_50%_100%,rgba(0,0,0,0.35),transparent_65%)]" />

      <SprocketColumn side="left" />
      <SprocketColumn side="right" />

      <CornerBracket position="tl" />
      <CornerBracket position="tr" />
      <CornerBracket position="bl" />
      <CornerBracket position="br" />

      {!reducedMotion && (
        <div
          className="absolute inset-x-0 h-24 bg-gradient-to-b from-transparent via-white/10 to-transparent animate-scan-sweep"
          aria-hidden
        />
      )}

      <div className="absolute bottom-9 left-1/2 -translate-x-1/2 font-plex-mono text-[10px] uppercase tracking-[0.2em] text-white/40">
        FRAME {String(frame).padStart(6, '0')} · 24 FPS · REC
      </div>
    </div>
  )
}

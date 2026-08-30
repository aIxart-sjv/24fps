import { Suspense, lazy, useEffect, useRef, useState } from 'react'
import type { CCTVHandle } from './CCTVScene'

const CCTVScene = lazy(() => import('./CCTVScene').then((m) => ({ default: m.CCTVScene })))

interface Label {
  text: string
  top: string
  left?: string
  right?: string
  align: 'left' | 'right'
  at: number
}

const LABELS: Label[] = [
  { text: 'LENS MODULE', top: '18%', right: '2%', align: 'right', at: 0.2 },
  { text: 'IR ARRAY', top: '30%', right: '6%', align: 'right', at: 0.28 },
  { text: 'IMAGE SENSOR', top: '42%', left: '4%', align: 'left', at: 0.38 },
  { text: 'PROCESSOR UNIT', top: '58%', right: '4%', align: 'right', at: 0.48 },
  { text: 'STORAGE CHIP', top: '68%', left: '8%', align: 'left', at: 0.58 },
  { text: 'POWER SUPPLY', top: '76%', right: '10%', align: 'right', at: 0.64 },
  { text: 'NETWORK INTERFACE', top: '86%', left: '2%', align: 'left', at: 0.72 },
]

function labelOpacity(progress: number, at: number): number {
  return Math.max(0, Math.min(1, (progress - at) / 0.12))
}

/**
 * Owns the hover/tap interaction as plain DOM events on this wrapping div,
 * rather than 3D raycasting inside the canvas — the whole panel is the
 * "generous hit area" the spec calls for, and it sidesteps any fragility in
 * React Three Fiber's pointer-event pipeline for enter/leave detection.
 */
export function CCTVHero() {
  const [progress, setProgress] = useState(0)
  const [hovered, setHovered] = useState(false)
  const [hasHover, setHasHover] = useState(true)
  const handleRef = useRef<CCTVHandle | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const hoveredRef = useRef(false)

  function setHoveredState(next: boolean) {
    hoveredRef.current = next
    setHovered(next)
  }

  useEffect(() => {
    setHasHover(window.matchMedia('(hover: hover) and (pointer: fine)').matches)
  }, [])

  useEffect(() => {
    if (hasHover || !hovered) return
    function onDocPointerDown(e: PointerEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setHoveredState(false)
        handleRef.current?.reverse()
      }
    }
    document.addEventListener('pointerdown', onDocPointerDown)
    return () => document.removeEventListener('pointerdown', onDocPointerDown)
  }, [hasHover, hovered])

  const metadataOpacity = Math.max(0, Math.min(1, (progress - 0.78) / 0.15))

  return (
    <div
      ref={containerRef}
      className="relative h-full w-full"
      onMouseEnter={
        hasHover
          ? () => {
              setHoveredState(true)
              handleRef.current?.play()
            }
          : undefined
      }
      onMouseLeave={
        hasHover
          ? () => {
              setHoveredState(false)
              handleRef.current?.reverse()
            }
          : undefined
      }
      onClick={
        !hasHover
          ? () => {
              const next = !hoveredRef.current
              setHoveredState(next)
              if (next) handleRef.current?.play()
              else handleRef.current?.reverse()
            }
          : undefined
      }
    >
      <Suspense fallback={<div className="h-full w-full" />}>
        <CCTVScene
          onProgress={setProgress}
          handleRef={handleRef}
          onReady={() => {
            // The user may have already hovered/tapped before the lazy-loaded
            // scene finished mounting — replay that intent now that the
            // timeline actually exists, instead of silently dropping it.
            if (hoveredRef.current) handleRef.current?.play()
          }}
        />
      </Suspense>

      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        {LABELS.map((label) => {
          const opacity = labelOpacity(progress, label.at)
          if (opacity <= 0) return null
          return (
            <div
              key={label.text}
              className="absolute flex items-center gap-2 font-plex-mono text-[10px] uppercase tracking-[0.15em] text-white transition-opacity"
              style={{
                top: label.top,
                left: label.left,
                right: label.right,
                opacity,
                flexDirection: label.align === 'right' ? 'row-reverse' : 'row',
              }}
            >
              <span className="h-px w-6 bg-forensic-yellow/70" />
              <span className="rounded-sm border border-white/20 bg-black/40 px-1.5 py-0.5 backdrop-blur-sm">
                {label.text}
              </span>
            </div>
          )
        })}

        <div
          className="absolute bottom-[4%] left-1/2 w-[min(90%,320px)] -translate-x-1/2 rounded-md border border-white/15 bg-black/50 p-3 font-plex-mono text-[10px] leading-relaxed text-white/90 backdrop-blur-sm transition-opacity"
          style={{ opacity: metadataOpacity }}
        >
          <div className="mb-1.5 flex items-center gap-1.5 text-forensic-yellow">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-forensic-yellow" />
            EVIDENCE SOURCE — DEMO ANALYSIS
          </div>
          <div className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-white/70">
            <span>CAMERA ID</span>
            <span className="text-white">CAM-24FPS-07</span>
            <span>TYPE</span>
            <span className="text-white">IP CAMERA</span>
            <span>RESOLUTION</span>
            <span className="text-white">4K ULTRA HD</span>
            <span>FRAME RATE</span>
            <span className="text-white">24 FPS</span>
            <span>STATUS</span>
            <span className="text-white">RECORDING</span>
            <span>HASH SHA256</span>
            <span className="truncate text-white">a3f5c2e9b1d4...7d8e9f</span>
          </div>
        </div>

        <div
          className="absolute left-1/2 top-[6%] -translate-x-1/2 rounded-full border border-white/25 bg-black/40 px-2.5 py-1 font-plex-mono text-[9px] uppercase tracking-[0.2em] text-white/70 backdrop-blur-sm transition-opacity"
          style={{ opacity: hovered ? Math.min(1, progress / 0.1) : 0 }}
        >
          Inspecting Evidence Source
        </div>
      </div>

      {!hovered && (
        <div className="pointer-events-none absolute bottom-[8%] left-1/2 -translate-x-1/2 font-plex-mono text-[9px] uppercase tracking-[0.2em] text-white/35">
          {hasHover ? 'Hover to Inspect' : 'Tap to Inspect'}
        </div>
      )}
    </div>
  )
}

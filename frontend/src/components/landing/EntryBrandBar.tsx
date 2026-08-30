/**
 * Shared brand bar for the Landing and Login pages: 24FPS top-left, CBI
 * top-right. No CBI logo asset exists anywhere in this repository (checked
 * frontend/public, frontend/src, and the whole project tree) — this renders
 * a plain typographic lockup, not a fabricated seal or emblem, as an
 * explicit placeholder until the real asset is supplied.
 */
export function EntryBrandBar() {
  return (
    <div className="relative z-10 flex items-start justify-between px-6 pt-6 sm:px-10 sm:pt-8">
      <div className="leading-none">
        <p className="font-plex text-lg font-bold tracking-tight text-white">24FPS</p>
        <p className="mt-1 font-plex-mono text-[9px] uppercase tracking-[0.2em] text-white/60">
          Forensic Intelligence System
        </p>
      </div>
      <div className="text-right leading-none">
        <p className="font-plex text-lg font-bold tracking-tight text-white">CBI</p>
        <p className="mt-1 font-plex-mono text-[9px] uppercase tracking-[0.2em] text-white/60">
          Central Bureau of Investigation
        </p>
      </div>
    </div>
  )
}

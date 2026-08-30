import { Link } from 'react-router-dom'
import { ArrowRight } from 'lucide-react'
import { EntryBrandBar } from '@/components/landing/EntryBrandBar'
import { ForensicBackdrop } from '@/components/landing/ForensicBackdrop'
import { CCTVHero } from '@/components/landing/CCTVHero'

export function Landing() {
  return (
    <div className="relative flex min-h-screen flex-col overflow-hidden bg-gradient-to-b from-forensic-red to-forensic-red-deep font-plex">
      <ForensicBackdrop />

      <EntryBrandBar />

      <div className="relative z-10 flex flex-1 flex-col items-center gap-4 px-6 py-6 sm:px-10 lg:flex-row lg:gap-10 lg:py-0 lg:px-16">
        <div className="flex w-full flex-col justify-center lg:w-[46%] lg:shrink-0">
          <h1 className="max-w-xl text-[13vw] font-extrabold uppercase leading-[0.92] tracking-tight text-forensic-ink sm:text-6xl lg:text-7xl">
            Every Frame
            <br />
            Tells a Story.
          </h1>
          <p className="mt-6 max-w-md font-plex-mono text-sm font-medium uppercase tracking-wide text-white/90 sm:text-lg">
            Acquire. Recover. Analyze. Verify. Report.
          </p>
        </div>

        <div className="relative h-[320px] w-full sm:h-[420px] lg:h-[560px] lg:flex-1">
          <CCTVHero />
        </div>
      </div>

      <div className="relative z-10 flex justify-center px-6 pb-8 sm:justify-end sm:px-10 sm:pb-14">
        <Link
          to="/login"
          className="group inline-flex items-center gap-2.5 rounded-md bg-forensic-yellow px-7 py-4 font-plex text-sm font-bold uppercase tracking-widest text-forensic-ink shadow-[0_8px_30px_-8px_rgba(0,0,0,0.6)] transition-transform hover:-translate-y-0.5"
        >
          Enter Platform
          <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
        </Link>
      </div>
    </div>
  )
}

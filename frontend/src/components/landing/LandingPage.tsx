import React from 'react';
import { Logo24FPS, LogoCBI } from '../Logos';
import { ArrowRight } from 'lucide-react';

interface LandingPageProps {
  onEnter?: () => void;
  onNavigate?: (path: string) => void;
}

export const LandingPage: React.FC<LandingPageProps> = ({ onEnter, onNavigate }) => {
  const handleEnter = () => {
    if (onEnter) {
      onEnter();
    } else if (onNavigate) {
      onNavigate('/login');
    }
  };

  return (
    <div className="min-h-screen w-full bg-[#c91818] text-white flex flex-col justify-between p-6 sm:p-10 md:p-14 lg:p-16 select-none relative overflow-hidden">
      {/* Subtle background textural grid for precision engineering feel */}
      <div 
        className="absolute inset-0 opacity-[0.07] pointer-events-none"
        style={{
          backgroundImage: `linear-gradient(#000 1px, transparent 1px), linear-gradient(90deg, #000 1px, transparent 1px)`,
          backgroundSize: '40px 40px'
        }}
      />

      {/* TOP HEADER: 24FPS Logo & CBI Logo */}
      <header className="flex items-center justify-between w-full relative z-10">
        <div className="flex items-center gap-3">
          <Logo24FPS variant="dark" className="h-10 sm:h-12 md:h-14 w-auto" />
        </div>
        <div className="flex items-center gap-3">
          {/* Subtle dark translucent backing container (75-80% opacity) for CBI official emblem */}
          <div className="bg-black/80 rounded px-2.5 py-1.5 sm:px-3 sm:py-2 border border-black/20 flex items-center justify-center">
            <LogoCBI className="h-10 sm:h-12 md:h-14 w-auto" />
          </div>
        </div>
      </header>

      {/* HERO CENTER / LEFT */}
      <main className="my-auto py-12 md:py-16 max-w-4xl relative z-10">
        {/* Large Headline */}
        <h1 className="text-4xl sm:text-6xl md:text-7xl lg:text-8xl font-black tracking-tight text-black leading-[0.92] font-sans drop-shadow-sm">
          EVERY FRAME
          <br />
          TELLS A STORY.
        </h1>

        {/* Supporting Workflow Statement */}
        <div className="mt-8 sm:mt-10 md:mt-12 text-lg sm:text-xl md:text-2xl lg:text-3xl text-white font-medium tracking-tight font-sans space-y-1">
          <p>Acquire. Recover. Analyze.</p>
          <p>Verify. Report.</p>
        </div>

        {/* Minimal Sub-tag for Technical Rigor */}
        <div className="mt-6 sm:mt-8 inline-flex items-center gap-2 px-3 py-1 rounded bg-black/20 text-white/90 text-xs sm:text-sm font-mono border border-black/10">
          <span className="w-2 h-2 rounded-full bg-yellow-400 animate-pulse" />
          <span>UNIFIED DIGITAL FORENSICS PLATFORM FOR CCTV EVIDENCE</span>
        </div>
      </main>

      {/* BOTTOM RIGHT: Exactly ONE Primary Yellow CTA Button */}
      <footer className="w-full flex justify-end items-center relative z-10 pt-6 border-t border-black/10">
        <button
          onClick={handleEnter}
          className="group relative inline-flex items-center justify-center gap-3 px-8 sm:px-10 py-4 sm:py-5 rounded text-base sm:text-lg font-bold font-sans bg-[#facc15] hover:bg-[#eab308] text-black shadow-xl hover:shadow-2xl transition-all duration-200 cursor-pointer active:scale-[0.98] border border-yellow-300/40"
        >
          <span className="tracking-wider uppercase font-extrabold text-sm sm:text-base">
            ENTER PLATFORM
          </span>
          <ArrowRight className="w-5 h-5 group-hover:translate-x-1.5 transition-transform duration-200" />
        </button>
      </footer>
    </div>
  );
};

import React from 'react';

interface LogoProps {
  className?: string;
  variant?: 'light' | 'dark' | 'monochrome' | 'auto';
  showText?: boolean;
}

/**
 * 24FPS Official Brand Asset (Team / Product Identity)
 * Faithful recreation of the uploaded 24 logo with stylized cuts
 */
export const Logo24FPS: React.FC<LogoProps> = ({ className = 'h-8 w-auto', variant = 'auto' }) => {
  const isDark = variant === 'dark';
  const fill = variant === 'monochrome' ? 'currentColor' : isDark ? '#ffffff' : '#171717';

  return (
    <div className={`inline-flex items-center gap-2 select-none ${className}`}>
      <svg
        viewBox="0 0 200 160"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className="h-full w-auto max-h-full aspect-[5/4]"
      >
        {/* Stylized '2' */}
        <path
          d="M32 68C32 36 54 18 90 18C124 18 144 36 144 62C144 76 136 90 120 104L76 142H146L142 160H28L28 144L84 96C98 84 106 74 106 62C106 48 96 36 78 36C60 36 50 48 50 68H32Z"
          fill={fill}
        />
        {/* Stylized '4' overlapping with sharp cuts */}
        <path
          d="M102 60L52 130H106V160H126V130H158V112H126V60H102ZM106 82V112H76L106 82Z"
          fill={fill}
        />
        {/* Dynamic accent cut angle characteristic of 24FPS mark */}
        <path
          d="M140 102L188 102L162 144L114 144L140 102Z"
          fill={fill}
        />
      </svg>
      <div className="flex flex-col justify-center">
        <span className="font-bold text-lg leading-tight tracking-tight font-sans" style={{ color: fill }}>
          24FPS
        </span>
        <span className="text-[9px] uppercase tracking-widest font-mono opacity-70 leading-none" style={{ color: fill }}>
          FORENSICS
        </span>
      </div>
    </div>
  );
};

/**
 * CBI Official Brand Asset (Institutional / Law-Enforcement Identity)
 * Central Bureau of Investigation emblem with golden laurels and red banner
 */
export const LogoCBI: React.FC<LogoProps> = ({ className = 'h-9 w-auto' }) => {
  return (
    <div className={`inline-flex items-center gap-2.5 select-none ${className}`}>
      <svg
        viewBox="0 0 300 320"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className="h-full w-auto max-h-full aspect-[300/320]"
      >
        {/* Top Arch Banner - Deep Navy Blue */}
        <path
          d="M 45 105 A 115 115 0 0 1 255 105 L 240 120 A 95 95 0 0 0 60 120 Z"
          fill="#1e3a8a"
          stroke="#ca8a04"
          strokeWidth="2.5"
        />
        <text
          x="150"
          y="70"
          fill="#ffffff"
          fontSize="11"
          fontWeight="bold"
          fontFamily="IBM Plex Sans, sans-serif"
          textAnchor="middle"
          letterSpacing="1.2"
        >
          CENTRAL BUREAU OF INVESTIGATION
        </text>
        <text
          x="150"
          y="88"
          fill="#1d4ed8"
          fontSize="15"
          fontWeight="900"
          fontFamily="IBM Plex Sans, sans-serif"
          textAnchor="middle"
          letterSpacing="2"
        >
          INDIA
        </text>

        {/* Ashoka Lion Capital (Stylized Golden Emblem) */}
        <g id="ashoka-lions">
          {/* Base Pedestal */}
          <rect x="110" y="195" width="80" height="12" rx="2" fill="#ca8a04" />
          <circle cx="150" cy="201" r="4" fill="#1e3a8a" />
          {/* Central & Side Lions */}
          <path
            d="M 125 195 C 120 160 125 130 140 110 C 145 105 155 105 160 110 C 175 130 180 160 175 195 Z"
            fill="#eab308"
            stroke="#a16207"
            strokeWidth="1.5"
          />
          {/* Mane and detail accents */}
          <path d="M 135 135 Q 150 145 165 135" stroke="#854d0e" strokeWidth="2" fill="none" />
          <path d="M 132 155 Q 150 168 168 155" stroke="#854d0e" strokeWidth="2" fill="none" />
          <path d="M 136 175 Q 150 185 164 175" stroke="#854d0e" strokeWidth="2" fill="none" />
          {/* Motto below pedestal */}
          <text
            x="150"
            y="218"
            fill="#a16207"
            fontSize="9"
            fontWeight="bold"
            fontFamily="IBM Plex Sans, sans-serif"
            textAnchor="middle"
          >
            सत्यमेव जयते
          </text>
        </g>

        {/* Golden Laurel Wreath (Flanking Leaves) */}
        <g id="laurel-wreath" stroke="#ca8a04" fill="#eab308" strokeWidth="1">
          {/* Left Leaves */}
          <path d="M 60 125 C 45 165 48 215 90 250 C 75 220 70 175 80 140 Z" />
          <path d="M 75 160 C 60 180 65 210 95 235 C 80 205 85 180 90 165 Z" />
          <path d="M 95 195 C 85 220 95 240 120 255 C 105 235 105 215 110 200 Z" />

          {/* Right Leaves */}
          <path d="M 240 125 C 255 165 252 215 210 250 C 225 220 230 175 220 140 Z" />
          <path d="M 225 160 C 240 180 235 210 205 235 C 220 205 215 180 210 165 Z" />
          <path d="M 205 195 C 215 220 205 240 180 255 C 195 235 195 215 190 200 Z" />
        </g>

        {/* Bottom Red Banner with Motto */}
        <g id="bottom-ribbon">
          <path
            d="M 15 225 L 45 285 L 150 310 L 255 285 L 285 225 L 260 235 L 235 270 L 150 290 L 65 270 L 40 235 Z"
            fill="#dc2626"
            stroke="#991b1b"
            strokeWidth="1.5"
          />
          {/* Ribbon Text: INDUSTRY IMPARTIALITY INTEGRITY */}
          <text
            x="48"
            y="262"
            fill="#ffffff"
            fontSize="9"
            fontWeight="bold"
            fontFamily="IBM Plex Sans, sans-serif"
            transform="rotate(65 48 262)"
          >
            INDUSTRY
          </text>
          <text
            x="150"
            y="288"
            fill="#ffffff"
            fontSize="10"
            fontWeight="900"
            fontFamily="IBM Plex Sans, sans-serif"
            textAnchor="middle"
            letterSpacing="1.8"
          >
            IMPARTIALITY
          </text>
          <text
            x="252"
            y="262"
            fill="#ffffff"
            fontSize="9"
            fontWeight="bold"
            fontFamily="IBM Plex Sans, sans-serif"
            transform="rotate(-65 252 262)"
          >
            INTEGRITY
          </text>
        </g>
      </svg>
      <div className="flex flex-col justify-center">
        <span className="font-bold text-xs leading-tight tracking-wider text-slate-800 dark:text-slate-100 font-sans">
          CBI
        </span>
        <span className="text-[8px] uppercase tracking-widest font-mono text-slate-500 dark:text-slate-400 leading-none">
          GOVT OF INDIA
        </span>
      </div>
    </div>
  );
};

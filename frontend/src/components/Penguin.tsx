import { useMotionProfile, type Motion } from "@/hooks/useMotion";
import "./penguin.css";

export type PenguinMood = "loading" | "slow" | "offline" | "error" | "empty";

interface PenguinProps {
  mood: PenguinMood;
  size?: number;
  motion?: Motion;
  className?: string;
}

const PUPIL: Record<PenguinMood, { dx: number; dy: number; r: number }> = {
  loading: { dx: 2, dy: 1, r: 3.4 },
  slow: { dx: 0, dy: 3.5, r: 3.4 },
  offline: { dx: 0, dy: 0, r: 2.2 },
  error: { dx: 0, dy: 0, r: 0 },
  empty: { dx: 2, dy: -2.5, r: 3.2 },
};

function Eyes({ mood }: { mood: PenguinMood }) {
  const p = PUPIL[mood];
  return (
    <g>
      <circle className="pg-white" cx="50" cy="44" r="8.5" />
      <circle className="pg-white" cx="70" cy="44" r="8.5" />
      {mood === "error" ? (
        <path className="pg-x" d="M46 40 L54 48 M54 40 L46 48 M66 40 L74 48 M74 40 L66 48" />
      ) : (
        <>
          <circle className="pg-ink" cx={50 + p.dx} cy={44 + p.dy} r={p.r} />
          <circle className="pg-ink" cx={70 + p.dx} cy={44 + p.dy} r={p.r} />
        </>
      )}
      {mood === "slow" && (
        <>
          <path className="pg-lid" d="M41.5 44 A8.5 8.5 0 0 1 58.5 44 Z" />
          <path className="pg-lid" d="M61.5 44 A8.5 8.5 0 0 1 78.5 44 Z" />
        </>
      )}
      {mood === "offline" && (
        <path className="pg-brow" d="M43 35 Q50 31 57 34 M63 34 Q70 31 77 35" />
      )}
    </g>
  );
}

function Stick({ mood }: { mood: PenguinMood }) {
  if (mood === "error") {
    return (
      <g>
        <path className="pg-wood" d="M99 106 L99 83" />
        <path className="pg-splinter" d="M99 83 L96.5 78.5 M99 83 L102.5 79" />
        <path className="pg-wood" d="M104 106 L117 100" />
      </g>
    );
  }
  if (mood === "empty") {
    return (
      <g>
        <path className="pg-wood" d="M99 106 L99 48" />
        <rect className="pg-flag" x="99" y="48" width="17" height="12" rx="1.5" />
      </g>
    );
  }
  return (
    <g>
      <path className="pg-wood" d="M99 106 L99 60" />
      <circle className="pg-cap" cx="99" cy="58" r="3.4" />
      {mood === "offline" && (
        <>
          <path className="pg-cable" d="M99 58 C110 51 115 63 109 71" />
          <rect
            className="pg-plug"
            x="105"
            y="70"
            width="8"
            height="6"
            rx="1.2"
            transform="rotate(40 109 73)"
          />
          <path className="pg-spark" d="M103 79 L99 83" />
          <path className="pg-spark pg-spark-b" d="M108 80 L108 86" />
          <path className="pg-spark pg-spark-c" d="M113 78 L117 82" />
        </>
      )}
    </g>
  );
}

export default function Penguin({ mood, size = 120, motion, className }: PenguinProps) {
  const profile = useMotionProfile();
  const m = motion ?? profile;
  const cls = [
    "penguin",
    `penguin--${mood}`,
    m !== "none" ? "penguin--animated" : "",
    m === "lite" ? "penguin--lite" : "",
    className ?? "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <svg
      className={cls}
      width={size}
      height={size}
      viewBox="0 0 120 120"
      aria-hidden="true"
      focusable="false"
    >
      <ellipse className="pg-shadow" cx="60" cy="109" rx="30" ry="4" />
      <Stick mood={mood} />
      <g transform={mood === "slow" ? "rotate(7 60 104)" : undefined}>
        <g className="pg-rock">
          <ellipse className="pg-foot pg-foot-l" cx="48" cy="106" rx="10" ry="4.5" />
          <ellipse className="pg-foot pg-foot-r" cx="72" cy="106" rx="10" ry="4.5" />
          <ellipse className="pg-body" cx="60" cy="64" rx="30" ry="40" />
          <ellipse className="pg-belly" cx="60" cy="74" rx="19" ry="26" />
          <path className="pg-body pg-flip-l" d="M31 56 C19 62 17 80 24 90 C31 83 34 70 35 60 Z" />
          <path className="pg-body pg-flip-r" d="M89 56 C101 62 103 80 96 90 C89 83 86 70 85 60 Z" />
          <Eyes mood={mood} />
          <path className="pg-beak" d="M54 53 Q60 50 66 53 Q64 61 60 62 Q56 61 54 53 Z" />
        </g>
      </g>
      {mood === "slow" && <path className="pg-drop" d="M88 26 Q92 33 88 37 Q84 33 88 26 Z" />}
    </svg>
  );
}

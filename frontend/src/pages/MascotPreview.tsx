import { useState } from "react";
import StateView from "@/components/StateView";
import type { PenguinMood } from "@/components/Penguin";
import type { Motion } from "@/hooks/useMotion";
import { STATE_COPY } from "@/lib/stateCopy";

const MOODS: PenguinMood[] = ["loading", "slow", "offline", "error", "empty"];
const MOTIONS: Motion[] = ["full", "lite", "none"];

function Row({ light, motion }: { light: boolean; motion: Motion }) {
  return (
    <div
      className={light ? "light" : undefined}
      style={{ background: "var(--bg-base)", color: "var(--text-primary)", padding: 16 }}
    >
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
          gap: 8,
          alignItems: "start",
        }}
      >
        {MOODS.map((mood) => (
          <StateView
            key={mood}
            mood={mood}
            motion={motion}
            title={STATE_COPY[mood].title}
            hint={STATE_COPY[mood].hint}
            action={
              mood === "error" || mood === "offline"
                ? { label: "Try again", onClick: () => undefined }
                : undefined
            }
          />
        ))}
      </div>
    </div>
  );
}

export default function MascotPreview() {
  const [motion, setMotion] = useState<Motion>("full");
  return (
    <div style={{ background: "var(--bg-base)", minHeight: "100vh", color: "var(--text-primary)" }}>
      <div style={{ display: "flex", gap: 16, padding: 16, fontSize: 13 }}>
        <span>Motion:</span>
        {MOTIONS.map((m) => (
          <button
            key={m}
            type="button"
            aria-pressed={motion === m}
            onClick={() => setMotion(m)}
            style={{
              background: "none",
              border: 0,
              padding: 0,
              color: motion === m ? "var(--brand)" : "var(--text-secondary)",
              fontWeight: motion === m ? 700 : 400,
              cursor: "pointer",
            }}
          >
            {m}
          </button>
        ))}
      </div>
      <Row light={false} motion={motion} />
      <Row light motion={motion} />
    </div>
  );
}

import { useState } from "react";
import StateView from "@/components/StateView";
import type { PenguinMood } from "@/components/Penguin";
import { useRegionState } from "@/hooks/useRegionState";
import type { Motion } from "@/hooks/useMotion";
import { STATE_COPY } from "@/lib/stateCopy";
import { useConnectionStore } from "@/store/connection";

const MOODS: PenguinMood[] = ["loading", "slow", "offline", "error", "empty"];
const MOTIONS: Motion[] = ["full", "lite", "none"];
type Mode = "pending" | "error" | "empty" | "data";
const MODES: Mode[] = ["pending", "error", "empty", "data"];
const LINKS = ["online", "offline", "unreachable"] as const;

function Choice({ active, label, onClick }: { active: boolean; label: string; onClick: () => void }) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      style={{
        background: "none",
        border: 0,
        padding: 0,
        color: active ? "var(--brand)" : "var(--text-secondary)",
        fontWeight: active ? 700 : 400,
        cursor: "pointer",
      }}
    >
      {label}
    </button>
  );
}

function Simulator() {
  const [mode, setMode] = useState<Mode>("pending");
  const [link, setLinkName] = useState<(typeof LINKS)[number]>("online");
  const view = useRegionState({
    pending: mode === "pending",
    error: mode === "error",
    empty: mode === "empty",
    retry: () => setMode("pending"),
  });

  function setLink(l: (typeof LINKS)[number]) {
    setLinkName(l);
    useConnectionStore.setState(
      l === "offline"
        ? { browserOnline: false }
        : { browserOnline: true, failures: l === "unreachable" ? 2 : 0 }
    );
  }

  return (
    <div style={{ padding: 16, fontSize: 13 }}>
      <div style={{ display: "flex", gap: 16, marginBottom: 8 }}>
        <span>Region:</span>
        {MODES.map((m) => (
          <Choice key={m} active={mode === m} label={m} onClick={() => setMode(m)} />
        ))}
      </div>
      <div style={{ display: "flex", gap: 16 }}>
        <span>Link:</span>
        {LINKS.map((l) => (
          <Choice key={l} active={link === l} label={l} onClick={() => setLink(l)} />
        ))}
      </div>
      <div style={{ minHeight: 260, marginTop: 8 }}>
        {view.kind === "state" ? (
          <StateView {...view.props} />
        ) : (
          <p style={{ color: "var(--text-muted)", padding: 32 }}>
            {view.kind === "quiet" ? "Quiet phase, nothing shown yet." : "Data would render here."}
          </p>
        )}
      </div>
    </div>
  );
}

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
          <Choice key={m} active={motion === m} label={m} onClick={() => setMotion(m)} />
        ))}
      </div>
      <Row light={false} motion={motion} />
      <Row light motion={motion} />
      <Simulator />
    </div>
  );
}

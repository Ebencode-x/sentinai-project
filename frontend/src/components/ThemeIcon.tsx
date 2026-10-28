import type { CSSProperties } from "react";
import { Sun, Moon } from "lucide-react";
import { useMotionProfile } from "@/hooks/useMotion";

const SIZE = 18;

/** Thin sun and moon stacked in one spot. The inactive one turns and fades out. */
export default function ThemeIcon({ dark }: { dark: boolean }) {
  const m = useMotionProfile();
  const time = m === "none" ? "0s" : m === "full" ? "0.4s" : "0.2s";
  const layer = (on: boolean, turn: number): CSSProperties => ({
    position: "absolute",
    inset: 0,
    opacity: on ? 1 : 0,
    transform: on ? "rotate(0deg) scale(1)" : `rotate(${turn}deg) scale(0.4)`,
    transition: `transform ${time} cubic-bezier(0.2, 0.8, 0.2, 1), opacity ${time} ease`,
  });
  return (
    <span aria-hidden="true" style={{ position: "relative", display: "inline-block", width: SIZE, height: SIZE }}>
      <Sun size={SIZE} strokeWidth={1.75} style={layer(dark, 90)} />
      <Moon size={SIZE} strokeWidth={1.75} style={layer(!dark, -90)} />
    </span>
  );
}

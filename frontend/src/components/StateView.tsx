import Penguin, { type PenguinMood } from "@/components/Penguin";
import type { Motion } from "@/hooks/useMotion";
import "./state-view.css";

interface StateViewProps {
  mood: PenguinMood;
  title: string;
  hint?: string;
  action?: { label: string; onClick: () => void };
  compact?: boolean;
  motion?: Motion;
}

export default function StateView({ mood, title, hint, action, compact, motion }: StateViewProps) {
  const urgent = mood === "error" || mood === "offline";
  return (
    <div
      className={compact ? "state-view state-view--compact" : "state-view"}
      role={urgent ? "alert" : "status"}
    >
      <Penguin mood={mood} size={compact ? 88 : 120} motion={motion} />
      <p className="state-view__title">{title}</p>
      {hint && <p className="state-view__hint">{hint}</p>}
      {action && (
        <button type="button" className="state-view__action" onClick={action.onClick}>
          {action.label}
        </button>
      )}
    </div>
  );
}

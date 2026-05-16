import clsx from "clsx";

interface Props { className?: string; rows?: number; }

export default function Skeleton({ className, rows = 1 }: Props) {
  return (
    <div className="space-y-2">
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          className={clsx(
            "animate-pulse rounded-sm bg-bg-card border border-bg-border",
            className ?? "h-12 w-full"
          )}
        />
      ))}
    </div>
  );
}

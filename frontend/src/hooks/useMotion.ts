import { useEffect, useRef, useState } from "react";

export type Motion = "full" | "lite" | "none";

const QUERIES = [
  "(prefers-reduced-motion: reduce)",
  "(hover: hover) and (pointer: fine)",
  "(min-width: 768px)",
];

function read(): Motion {
  if (typeof window === "undefined") return "none";
  const [reduce, fine, wide] = QUERIES.map((q) => window.matchMedia(q).matches);
  if (reduce) return "none";
  return fine && wide ? "full" : "lite";
}

/** full: desktop with a mouse. lite: phones and tablets. none: reduced motion. */
export function useMotionProfile(): Motion {
  const [m, setM] = useState<Motion>(read);
  useEffect(() => {
    const lists = QUERIES.map((q) => window.matchMedia(q));
    const on = () => setM(read());
    lists.forEach((l) => l.addEventListener("change", on));
    return () => lists.forEach((l) => l.removeEventListener("change", on));
  }, []);
  return m;
}

export function useInView<T extends Element>() {
  const ref = useRef<T>(null);
  const [seen, setSeen] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el || seen) return;
    if (typeof IntersectionObserver === "undefined") {
      setSeen(true);
      return;
    }
    const io = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          setSeen(true);
          io.disconnect();
        }
      },
      { threshold: 0.15 }
    );
    io.observe(el);
    return () => io.disconnect();
  }, [seen]);
  return [ref, seen] as const;
}

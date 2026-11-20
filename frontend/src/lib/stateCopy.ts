import type { PenguinMood } from "@/components/Penguin";

export const STATE_COPY: Record<PenguinMood, { title: string; hint: string }> = {
  loading: { title: "Loading", hint: "Fetching your data." },
  slow: {
    title: "Still working",
    hint: "The server is waking up. This can take about a minute.",
  },
  offline: {
    title: "You are offline",
    hint: "Check your connection. We will reload when it is back.",
  },
  error: { title: "Something broke", hint: "The request failed. Try again in a moment." },
  empty: {
    title: "Nothing here yet",
    hint: "Items will show up here when there is something to see.",
  },
};

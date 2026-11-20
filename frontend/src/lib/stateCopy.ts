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

export const COPY_UNREACHABLE = {
  title: "Server not answering",
  hint: "It may be waking up. Try again in a moment.",
};

export const COPY_TIMEOUT = {
  title: "This is taking too long",
  hint: "The server did not answer in time.",
};

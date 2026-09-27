import { useEffect, useState } from "react";

/** Seconds elapsed while `active` — used to be honest about how long AI triage takes. */
export function useElapsedSeconds(active: boolean): number {
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    if (!active) return;
    const started = Date.now();
    const id = window.setInterval(() => setSeconds(Math.floor((Date.now() - started) / 1000)), 250);
    return () => {
      window.clearInterval(id);
      setSeconds(0);
    };
  }, [active]);
  return seconds;
}

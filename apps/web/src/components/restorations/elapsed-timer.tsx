"use client";

import { useEffect, useState } from "react";

// Advancing elapsed-time readout for the synchronous colorize POST. DeOldify on
// CPU can take seconds to a few minutes, and a static "Colorizing…" spinner
// looks frozen — a counter that visibly ticks up reassures the user the run is
// still progressing. Mounted only while a run is in flight, so it resets each
// time. `aria-live` announces the progress to assistive tech.
function format(totalSeconds: number): string {
  const m = Math.floor(totalSeconds / 60);
  const s = totalSeconds % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export function ElapsedTimer({ className }: { className?: string }) {
  const [seconds, setSeconds] = useState(0);

  useEffect(() => {
    const startedAt = Date.now();
    const id = setInterval(() => {
      setSeconds(Math.floor((Date.now() - startedAt) / 1000));
    }, 1000);
    return () => clearInterval(id);
  }, []);

  return (
    <p
      className={className}
      role="status"
      aria-live="polite"
      aria-label={`Elapsed ${format(seconds)}`}
    >
      Elapsed{" "}
      <span className="font-mono tabular-nums text-foreground">
        {format(seconds)}
      </span>
    </p>
  );
}

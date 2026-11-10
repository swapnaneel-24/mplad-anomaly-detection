// Loading indicator: a single muted line. No spinner, no shimmer.
// `aria-busy` is set on the wrapping span when ariaBusy is true.

import { useEffect, useRef } from "react";

export interface LoadingProps {
  label?: string;
  ariaBusy?: boolean;
}

export function Loading({ label = "Loading…", ariaBusy = true }: LoadingProps): JSX.Element {
  const ref = useRef<HTMLSpanElement>(null);

  // Move focus to the loading region on mount so screen readers announce
  // the state change. The region is not focusable in the visual sense
  // (no focus ring) — tabindex=-1 allows programmatic focus only.
  useEffect(() => {
    ref.current?.focus();
  }, []);

  return (
    <span
      ref={ref}
      className="loading"
      role="status"
      aria-busy={ariaBusy}
      aria-live="polite"
      tabIndex={-1}
    >
      {label}
    </span>
  );
}

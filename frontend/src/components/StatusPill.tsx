// Reusable status pill. Renders the dot + label using the
// `.status-pill.<status>` classes from global.css.

import type { ConnectivityStatus } from "@/api/ConnectivityContext";

export interface StatusPillProps {
  status: ConnectivityStatus;
  label?: string;
  /** Optional longer description for screen readers. */
  ariaLabel?: string;
}

const DEFAULT_LABELS: Record<ConnectivityStatus, string> = {
  ready: "Ready",
  not_ready: "Not ready",
  unreachable: "Unreachable",
  unknown: "Checking…",
};

export function StatusPill({ status, label, ariaLabel }: StatusPillProps): JSX.Element {
  const text = label ?? DEFAULT_LABELS[status];
  return (
    <span
      className={`status-pill ${status}`}
      aria-label={ariaLabel ?? `API status: ${text.toLowerCase()}`}
    >
      {text}
    </span>
  );
}

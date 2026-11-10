// Backend connectivity context.
//
// Tracks the live API connectivity state for the header / sidebar status
// pill. Refreshes:
//   - on mount (initial liveness check);
//   - on a 30-second interval (background re-check);
//   - on demand (e.g. after a failed request, the user can click Retry).
//
// The state is one of: ready | not_ready | unreachable | unknown.
//
//   - ready: GET /health/live returned 200 AND GET /health/ready returned
//     200 with all checks "ready".
//   - not_ready: liveness OK but readiness returned 503 (one or more
//     configured required dependencies are unavailable).
//   - unreachable: GET /health/live failed with a network error or
//     non-2xx (the API process is down or unreachable).
//   - unknown: a request is in flight, or the previous request was
//     aborted/timed out.
//
// The connectivity state NEVER infers PostgreSQL availability from
// liveness alone (design system §13): readiness is checked separately.

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { getHealthLive, getHealthReady } from "@/api/endpoints";
import { ApiError } from "@/api/client";

export type ConnectivityStatus = "ready" | "not_ready" | "unreachable" | "unknown";

export interface ConnectivityState {
  status: ConnectivityStatus;
  /** Subsystem-level details from /health/ready (may be empty). */
  checks: { name: string; status: "ready" | "unavailable" }[];
  /** Backend version from /health/live (when reachable). */
  version: string | null;
  /** Last error from a failed probe (for the retry tooltip). */
  lastError: ApiError | null;
  /** True while a probe is in flight. */
  checking: boolean;
  /** Trigger an immediate re-probe. */
  refresh: () => void;
}

const ConnectivityContext = createContext<ConnectivityState | null>(null);

const REFRESH_INTERVAL_MS = 30_000;

export function ConnectivityProvider({ children }: { children: ReactNode }): ReactNode {
  const [status, setStatus] = useState<ConnectivityStatus>("unknown");
  const [checks, setChecks] = useState<ConnectivityState["checks"]>([]);
  const [version, setVersion] = useState<string | null>(null);
  const [lastError, setLastError] = useState<ApiError | null>(null);
  const [checking, setChecking] = useState<boolean>(false);
  const abortRef = useRef<AbortController | null>(null);

  const refresh = useCallback(() => {
    // Abort any in-flight probe.
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setChecking(true);
    setStatus("unknown");

    (async () => {
      try {
        const live = await getHealthLive(controller.signal);
        setVersion(live.version);
      } catch (err) {
        if (err instanceof ApiError && err.aborted) return;
        setVersion(null);
        setChecks([]);
        setLastError(err instanceof ApiError ? err : null);
        setStatus("unreachable");
        setChecking(false);
        return;
      }
      // Liveness OK; now probe readiness.
      try {
        const ready = await getHealthReady(controller.signal);
        setChecks(ready.checks.map((c) => ({ name: c.name, status: c.status })));
        setLastError(null);
        setStatus("ready");
      } catch (err) {
        if (err instanceof ApiError && err.aborted) return;
        if (err instanceof ApiError && err.status === 503) {
          // Readiness reported unavailable — extract the failed checks
          // from the envelope details when present.
          const details = err.details as
            | { failed_checks?: { name: string; status: string }[] }
            | undefined;
          const failed = details?.failed_checks ?? [];
          setChecks(failed.map((c) => ({ name: c.name, status: "unavailable" as const })));
          setLastError(null);
          setStatus("not_ready");
        } else {
          setChecks([]);
          setLastError(err instanceof ApiError ? err : null);
          setStatus("unreachable");
        }
      }
      setChecking(false);
    })();
  }, []);

  // Initial probe + interval.
  useEffect(() => {
    refresh();
    const id = setInterval(refresh, REFRESH_INTERVAL_MS);
    return () => {
      clearInterval(id);
      abortRef.current?.abort();
    };
  }, [refresh]);

  // Re-probe when the window regains focus (cheap, no surprise).
  useEffect(() => {
    const onFocus = () => refresh();
    window.addEventListener("focus", onFocus);
    return () => window.removeEventListener("focus", onFocus);
  }, [refresh]);

  const value = useMemo<ConnectivityState>(
    () => ({ status, checks, version, lastError, checking, refresh }),
    [status, checks, version, lastError, checking, refresh],
  );

  return (
    <ConnectivityContext.Provider value={value}>{children}</ConnectivityContext.Provider>
  );
}

/** Consume the auth context. Throws if used outside an AuthProvider. */
// eslint-disable-next-line react-refresh/only-export-components
export function useConnectivity(): ConnectivityState {
  const ctx = useContext(ConnectivityContext);
  if (!ctx) {
    throw new Error("useConnectivity must be used inside a ConnectivityProvider");
  }
  return ctx;
}

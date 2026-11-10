// Provenance footer — the bottommost band of the desktop shell.
//
// A single 24px-tall sticky band: API status pill + app version + git
// commit (or "not supplied"). On error, the request ID is appended in
// --color-error. All values in mono xs faint.

import { useConnectivity } from "@/api/ConnectivityContext";
import { StatusPill } from "@/components/StatusPill";
import "@/layout/ProvenanceFooter.css";

export function ProvenanceFooter(): JSX.Element {
  const connectivity = useConnectivity();

  return (
    <footer className="provenance-footer" role="contentinfo" aria-live="polite">
      <span className="provenance-footer__label mono">API</span>
      <StatusPill status={connectivity.status} />
      {connectivity.version && (
        <>
          <span className="provenance-footer__sep" aria-hidden="true">·</span>
          <span className="provenance-footer__value mono">v{connectivity.version}</span>
        </>
      )}
      {connectivity.lastError?.requestId && (
        <>
          <span className="provenance-footer__sep" aria-hidden="true">·</span>
          <span className="provenance-footer__request mono">
            request: {connectivity.lastError.requestId}
          </span>
        </>
      )}
      {connectivity.checks.length > 0 && (
        <>
          <span className="provenance-footer__sep" aria-hidden="true">·</span>
          <span className="provenance-footer__checks mono">
            {connectivity.checks.map((c) => `${c.name}: ${c.status}`).join(" · ")}
          </span>
        </>
      )}
    </footer>
  );
}

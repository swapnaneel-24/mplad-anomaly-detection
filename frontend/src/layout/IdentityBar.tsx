// Identity bar — the topmost band of the desktop shell.
//
// Single 40px-tall sticky row: PEIARS serif mark + subtitle on the left;
// environment + connectivity pill + user display name + role + Sign out
// on the right. The page title is NOT repeated here (it lives in the
// context strip).

import { useAuth } from "@/auth/AuthContext";
import { useConnectivity } from "@/api/ConnectivityContext";
import { StatusPill } from "@/components/StatusPill";
import "@/layout/IdentityBar.css";

export function IdentityBar(): JSX.Element {
  const { user, logout } = useAuth();
  const connectivity = useConnectivity();

  return (
    <header className="identity-bar" role="banner">
      <div className="identity-bar__brand">
        <span className="identity-bar__mark">PEIARS</span>
        <span className="identity-bar__sep" aria-hidden="true">·</span>
        <span className="identity-bar__subtitle">Anomaly Review Workbench</span>
      </div>
      <div className="identity-bar__session">
        <span className="identity-bar__env mono">
          {connectivity.version ? `v${connectivity.version}` : ""}
        </span>
        <StatusPill status={connectivity.status} />
        {user && (
          <>
            <span className="identity-bar__sep" aria-hidden="true">·</span>
            <span className="identity-bar__user-name">{user.display_name}</span>
            <span className="identity-bar__user-role mono">{user.role.toUpperCase()}</span>
            <button
              type="button"
              className="btn btn-secondary btn-compact"
              onClick={() => void logout()}
            >
              Sign out
            </button>
          </>
        )}
      </div>
    </header>
  );
}

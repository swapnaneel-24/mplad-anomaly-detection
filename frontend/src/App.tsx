// PEIARS React application root.
//
// Wires the auth + connectivity providers and the BrowserRouter. Route
// composition lives in `routes/index.tsx`; the AppShell (sidebar + header)
// is rendered by `<RequireAuth>` only when the user is authenticated, so
// the login screen and the connectivity-uncertainty screen are full-bleed.

import { BrowserRouter } from "react-router-dom";
import { AuthProvider } from "@/auth/AuthContext";
import { ConnectivityProvider } from "@/api/ConnectivityContext";
import { AppRoutes } from "@/routes";

export default function App(): JSX.Element {
  return (
    <BrowserRouter>
      <AuthProvider>
        <ConnectivityProvider>
          <AppRoutes />
        </ConnectivityProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}

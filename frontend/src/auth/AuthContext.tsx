// Authentication state machine for the PEIARS frontend.
//
// Implements PR-05A §11 (Browser authentication):
//
//   - Login: CSRF bootstrap → POST /auth/login with X-CSRF-Token; on
//     success, store the UserResponse and redirect.
//   - Session restoration: on app load, GET /auth/me; if it returns 200,
//     restore the session; if it returns 401, the user is anonymous; if
//     it fails with a network error or timeout, the state is `unknown`
//     (the user is NOT silently logged out — see design system §10.5).
//   - Logout: re-bootstrap CSRF if needed → POST /auth/logout with
//     X-CSRF-Token; on success (or a confirmed 401), clear local state.
//     Network errors do NOT clear local state — the UI reports the
//     failure honestly.
//
// The session token is NEVER in React state. It lives only in the
// HttpOnly cookie managed by the browser. React state holds only the
// sanitized UserResponse (id, username, display_name, role, permissions).
//
// Roles: viewer < reviewer < admin. The interface can adapt visible
// capabilities based on role, but backend authorization remains
// authoritative (see backend/app/auth/dependencies.py).

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

import type { LoginRequest, Role, UserResponse } from "@/api/contracts";
import {
  getCurrentUser,
  getCsrfToken,
  login as apiLogin,
  logout as apiLogout,
} from "@/api/endpoints";
import { ApiError } from "@/api/client";
import { hasCsrfCookie, readCsrfCookie } from "@/auth/csrf";

/** Auth state machine. `unknown` is distinct from `anonymous`. */
export type AuthStatus =
  | "loading" // initial /auth/me in flight
  | "authenticated" // /auth/me returned 200
  | "anonymous" // /auth/me returned 401
  | "unknown"; // /auth/me failed with network error / timeout

export interface AuthState {
  status: AuthStatus;
  user: UserResponse | null;
  /** Last connectivity-affecting error (for the connectivity banner). */
  lastError: ApiError | null;
}

export interface AuthContextValue extends AuthState {
  /** Restore the session on app load. Safe to call once. */
  restore: () => Promise<void>;
  /** Login with username/password. Resolves the post-login user. */
  login: (credentials: LoginRequest) => Promise<UserResponse>;
  /** Logout via the backend; clears local state only on confirmed logout. */
  logout: () => Promise<void>;
  /** Permission predicate (server-side role is authoritative). */
  hasPermission: (permission: string) => boolean;
  /** Role predicate (server-side role is authoritative). */
  isRole: (role: Role) => boolean;
  /** Refresh the user from /auth/me (e.g. after role change). */
  refresh: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

/** Role rank used only for UI affordances, never for authorization. */
const ROLE_RANK: Record<Role, number> = { viewer: 1, reviewer: 2, admin: 3 };

export function AuthProvider({ children }: { children: ReactNode }): ReactNode {
  const [state, setState] = useState<AuthState>({
    status: "loading",
    user: null,
    lastError: null,
  });

  // Track whether restore() has been called so we don't issue duplicate
  // /auth/me requests on re-renders.
  const restoreStartedRef = useRef(false);

  const restore = useCallback(async () => {
    if (restoreStartedRef.current) return;
    restoreStartedRef.current = true;
    setState((s) => ({ ...s, status: "loading" }));
    try {
      const user = await getCurrentUser();
      setState({ status: "authenticated", user, lastError: null });
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.isUnauthorized) {
          setState({ status: "anonymous", user: null, lastError: null });
          return;
        }
        // Network failure / timeout / 5xx → uncertainty, not logout.
        setState({ status: "unknown", user: null, lastError: err });
        return;
      }
      // Defensive: any non-ApiError is treated as uncertainty.
      setState({
        status: "unknown",
        user: null,
        lastError: new ApiError({
          status: 0,
          code: "REQUEST_FAILED",
          message: "Cannot reach the API. Check your connection and retry.",
          requestId: null,
          aborted: false,
          timedOut: false,
          network: true,
        }),
      });
    }
  }, []);

  const refresh = useCallback(async () => {
    try {
      const user = await getCurrentUser();
      setState({ status: "authenticated", user, lastError: null });
    } catch (err) {
      if (err instanceof ApiError && err.isUnauthorized) {
        setState({ status: "anonymous", user: null, lastError: null });
        return;
      }
      // On network error during refresh, keep the existing session; do
      // not silently log the user out.
      setState((s) => ({ ...s, lastError: err instanceof ApiError ? err : null }));
    }
  }, []);

  const login = useCallback(async (credentials: LoginRequest): Promise<UserResponse> => {
    // CSRF bootstrap: if the cookie is missing, fetch a fresh token first.
    if (!hasCsrfCookie()) {
      await getCsrfToken();
    }
    const csrfToken = readCsrfCookie();
    if (!csrfToken) {
      throw new ApiError({
        status: 0,
        code: "CSRF_TOKEN_INVALID",
        message: "CSRF token could not be initialized. Reload and try again.",
        requestId: null,
        aborted: false,
        timedOut: false,
        network: false,
      });
    }
    const user = await apiLogin(credentials, csrfToken);
    // The backend rotates the CSRF cookie on login (session-fixation
    // prevention, see backend/app/api/v1/auth.py). The new cookie is set
    // by the response; we do not need to re-read it here.
    setState({ status: "authenticated", user, lastError: null });
    return user;
  }, []);

  const logout = useCallback(async () => {
    // Re-bootstrap CSRF if needed (the cookie may have expired).
    if (!hasCsrfCookie()) {
      try {
        await getCsrfToken();
      } catch {
        // If we cannot even bootstrap CSRF, the backend is likely down.
        // Do NOT clear local state — report the failure honestly.
        setState((s) => ({
          ...s,
          lastError: new ApiError({
            status: 0,
            code: "REQUEST_FAILED",
            message: "Cannot reach the API to log out. Try again.",
            requestId: null,
            aborted: false,
            timedOut: false,
            network: true,
          }),
        }));
        return;
      }
    }
    const csrfToken = readCsrfCookie();
    if (!csrfToken) {
      // Cookie blocked. Treat as already-logged-out only if /auth/me
      // confirms 401; otherwise keep the session and surface an error.
      try {
        await getCurrentUser();
        // Still authenticated but cannot logout without CSRF — surface error.
        setState((s) => ({
          ...s,
          lastError: new ApiError({
            status: 0,
            code: "CSRF_TOKEN_INVALID",
            message: "CSRF cookie is blocked. Adjust browser settings and retry.",
            requestId: null,
            aborted: false,
            timedOut: false,
            network: false,
          }),
        }));
        return;
      } catch (err) {
        if (err instanceof ApiError && err.isUnauthorized) {
          setState({ status: "anonymous", user: null, lastError: null });
          return;
        }
        // Network error — keep state, surface error.
        setState((s) => ({ ...s, lastError: err instanceof ApiError ? err : null }));
        return;
      }
    }
    try {
      await apiLogout(csrfToken);
      setState({ status: "anonymous", user: null, lastError: null });
    } catch (err) {
      if (err instanceof ApiError && err.isUnauthorized) {
        // Server already considers us logged out (session expired).
        setState({ status: "anonymous", user: null, lastError: null });
        return;
      }
      // Any other failure (network, 5xx, CSRF mismatch) — do NOT claim
      // success. Surface the error; the user can retry.
      setState((s) => ({ ...s, lastError: err instanceof ApiError ? err : null }));
    }
  }, []);

  const hasPermission = useCallback(
    (permission: string): boolean => {
      const user = state.user;
      if (!user) return false;
      return user.permissions.includes(permission);
    },
    [state.user],
  );

  const isRole = useCallback(
    (role: Role): boolean => {
      const user = state.user;
      if (!user) return false;
      return ROLE_RANK[user.role] >= ROLE_RANK[role];
    },
    [state.user],
  );

  // Restore the session once on mount.
  useEffect(() => {
    void restore();
  }, [restore]);

  const value = useMemo<AuthContextValue>(
    () => ({ ...state, restore, login, logout, hasPermission, isRole, refresh }),
    [state, restore, login, logout, hasPermission, isRole, refresh],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

/** Consume the auth context. Throws if used outside an AuthProvider. */
// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used inside an AuthProvider");
  }
  return ctx;
}

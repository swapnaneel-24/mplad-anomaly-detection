// Login screen: CSRF bootstrap + credentialed POST /auth/login.
// Per SCREEN_DESIGN_NOTES.md §1. Single-column centered, max-width 420px.

import { useEffect, useState } from "react";
import { Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "@/auth/AuthContext";
import { useConnectivity } from "@/api/ConnectivityContext";
import { ApiError } from "@/api/client";
import { ErrorPanel } from "@/components/ErrorPanel";
import "@/pages/LoginPage.css";

const USERNAME_MIN = 3;
const USERNAME_MAX = 64;
const PASSWORD_MIN = 8;
const PASSWORD_MAX = 128;
const LOCKOUT_CLIENT_HOLD_SECONDS = 30;

interface LoginFormErrors {
  username?: string;
  password?: string;
}

export function LoginPage(): JSX.Element {
  const { status, login } = useAuth();
  const connectivity = useConnectivity();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [errors, setErrors] = useState<LoginFormErrors>({});
  const [submitError, setSubmitError] = useState<ApiError | null>(null);
  const [lockoutHoldUntil, setLockoutHoldUntil] = useState<number | null>(null);

  // Clear the client-side lockout hold after the timer expires.
  // NOTE: this useEffect must run before any early return so the hooks
  // order is stable across renders.
  useEffect(() => {
    if (lockoutHoldUntil === null) return;
    const remaining = lockoutHoldUntil - Date.now();
    if (remaining <= 0) {
      setLockoutHoldUntil(null);
      return;
    }
    const id = setTimeout(() => setLockoutHoldUntil(null), remaining);
    return () => clearTimeout(id);
  }, [lockoutHoldUntil]);

  // If already authenticated, redirect to the next page (or /overview).
  if (status === "authenticated") {
    const next = searchParams.get("next");
    const safeNext = next && next.startsWith("/") && !next.startsWith("//") ? next : "/overview";
    return <Navigate to={safeNext} replace />;
  }

  const validate = (): boolean => {
    const next: LoginFormErrors = {};
    if (username.length < USERNAME_MIN) {
      next.username = `Username must be at least ${USERNAME_MIN} characters.`;
    } else if (username.length > USERNAME_MAX) {
      next.username = `Username must be at most ${USERNAME_MAX} characters.`;
    }
    if (password.length < PASSWORD_MIN) {
      next.password = `Password must be at least ${PASSWORD_MIN} characters.`;
    } else if (password.length > PASSWORD_MAX) {
      next.password = `Password must be at most ${PASSWORD_MAX} characters.`;
    }
    setErrors(next);
    return Object.keys(next).length === 0;
  };

  const canSubmit =
    !submitting &&
    lockoutHoldUntil === null &&
    username.length >= USERNAME_MIN &&
    password.length >= PASSWORD_MIN;

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>): Promise<void> => {
    event.preventDefault();
    if (submitting || lockoutHoldUntil !== null) return;
    if (!validate()) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      await login({ username, password });
      const next = searchParams.get("next");
      const safeNext = next && next.startsWith("/") && !next.startsWith("//") ? next : "/overview";
      navigate(safeNext, { replace: true });
    } catch (err) {
      if (err instanceof ApiError) {
        setSubmitError(err);
        if (err.isRateLimited) {
          setLockoutHoldUntil(Date.now() + LOCKOUT_CLIENT_HOLD_SECONDS * 1000);
        }
      } else {
        setSubmitError(
          new ApiError({
            status: 0,
            code: "REQUEST_FAILED",
            message: "An unexpected error occurred. Please retry.",
            requestId: null,
            aborted: false,
            timedOut: false,
            network: true,
          }),
        );
      }
    } finally {
      setSubmitting(false);
    }
  };

  const connectivityHint =
    connectivity.status === "ready"
      ? "API reachable · ready"
      : connectivity.status === "not_ready"
        ? "API reachable · not ready"
        : connectivity.status === "unreachable"
          ? "API unreachable"
          : "Checking API…";

  return (
    <div className="login-page" role="main">
      <div className="login-page__card">
        <header className="login-page__brand">
          <h1 className="login-page__brand-name">PEIARS</h1>
          <p className="login-page__brand-subtitle">
            Public Expenditure &amp; Infrastructure Anomaly Review System
          </p>
          <hr className="login-page__rule" />
        </header>

        <p className="login-page__lede editorial-muted">
          A scientific workbench for examining anomalies in public-development
          datasets. Statistical anomalies surface evidence for human review; an
          anomaly flag never implies fraud.
        </p>

        <form className="login-page__form" onSubmit={handleSubmit} noValidate>
          <div className="field">
            <label htmlFor="login-username" className="field__label">
              Username
            </label>
            <input
              id="login-username"
              name="username"
              type="text"
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              onBlur={() => {
                if (username.length > 0 && username.length < USERNAME_MIN) {
                  setErrors((p) => ({ ...p, username: `At least ${USERNAME_MIN} characters.` }));
                }
              }}
              className="field__input"
              aria-invalid={errors.username ? "true" : "false"}
              aria-describedby={errors.username ? "login-username-error" : "login-username-helper"}
              disabled={submitting || lockoutHoldUntil !== null}
              required
              minLength={USERNAME_MIN}
              maxLength={USERNAME_MAX}
            />
            {errors.username ? (
              <p id="login-username-error" className="field__error">
                {errors.username}
              </p>
            ) : (
              <p id="login-username-helper" className="field__helper">
                {USERNAME_MIN}–{USERNAME_MAX} characters
              </p>
            )}
          </div>

          <div className="field">
            <label htmlFor="login-password" className="field__label">
              Password
            </label>
            <div className="field__input-row">
              <input
                id="login-password"
                name="password"
                type={showPassword ? "text" : "password"}
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                onBlur={() => {
                  if (password.length > 0 && password.length < PASSWORD_MIN) {
                    setErrors((p) => ({ ...p, password: `At least ${PASSWORD_MIN} characters.` }));
                  }
                }}
                className="field__input"
                aria-invalid={errors.password ? "true" : "false"}
                aria-describedby={errors.password ? "login-password-error" : "login-password-helper"}
                disabled={submitting || lockoutHoldUntil !== null}
                required
                minLength={PASSWORD_MIN}
                maxLength={PASSWORD_MAX}
              />
              <button
                type="button"
                className="field__toggle"
                onClick={() => setShowPassword((v) => !v)}
                aria-pressed={showPassword}
                aria-label={showPassword ? "Conceal typing" : "Reveal typing"}
                tabIndex={0}
              >
                {showPassword ? "Hide" : "Show"}
              </button>
            </div>
            {errors.password ? (
              <p id="login-password-error" className="field__error">
                {errors.password}
              </p>
            ) : (
              <p id="login-password-helper" className="field__helper">
                {PASSWORD_MIN}–{PASSWORD_MAX} characters
              </p>
            )}
          </div>

          <button
            type="submit"
            className="btn btn-primary btn-block"
            disabled={!canSubmit}
            aria-busy={submitting}
          >
            {submitting ? "Working…" : "Sign in"}
          </button>

          {submitError && (
            <ErrorPanel
              error={submitError}
              title={
                submitError.isRateLimited
                  ? "Too many attempts"
                  : submitError.isNetwork
                    ? "Connection problem"
                    : "Sign-in failed"
              }
            />
          )}

          {lockoutHoldUntil !== null && (
            <p className="login-page__hold mono">
              The form is temporarily held. Wait a few seconds before retrying.
            </p>
          )}
        </form>

        <p className="login-page__hint mono" aria-live="polite">
          {connectivityHint}
        </p>
      </div>
    </div>
  );
}

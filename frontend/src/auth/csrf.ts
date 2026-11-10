// CSRF token helpers.
//
// The PR-04 backend uses a signed double-submit CSRF mechanism (see
// backend/app/auth/tokens.py and backend/app/auth/dependencies.py):
//
//   - GET /api/v1/auth/csrf issues `{random}:{HMAC-SHA256(secret, random)}`
//     as a readable (non-HttpOnly) cookie named `peiars_csrf` AND returns
//     the same value in the JSON body.
//   - State-changing requests (POST /auth/login, POST /auth/logout) must
//     echo the value in the `X-CSRF-Token` header. The server compares
//     header == cookie (constant-time) and verifies the embedded HMAC.
//
// IMPORTANT: tokens are NOT bound to individual authenticated sessions.
// The signature covers only the random nonce; the same token remains
// valid across login and logout. The implementation and documentation
// deliberately avoid describing the tokens as session-bound.
//
// The frontend reads the cookie directly because:
//   1. the cookie is intentionally readable (the React client must echo
//      it in the X-CSRF-Token header — see backend/app/auth/cookies.py);
//   2. reading the cookie avoids keeping the token in JS memory or
//      localStorage, where it could leak via XSS;
//   3. it matches the documented React bootstrap flow.
//
// The session cookie (peiars_session) is HttpOnly and is NEVER read by
// this code.

import { CSRF_COOKIE_NAME, CSRF_HEADER } from "@/api/contracts";

/**
 * Read the CSRF token from the readable `peiars_csrf` cookie.
 *
 * Returns `null` when the cookie is absent (e.g. blocked by browser
 * settings, or never bootstrapped). The caller should re-bootstrap via
 * `getCsrfToken()` and retry.
 */
export function readCsrfCookie(): string | null {
  if (typeof document === "undefined" || !document.cookie) return null;
  // Cookie header is "name=value; name2=value2; ...". Splitting on the
  // delimiter and trimming handles values that themselves contain '='
  // (the CSRF token's HMAC hex digest never does, but this is robust).
  const parts = document.cookie.split(";");
  for (const part of parts) {
    const [rawName, ...rest] = part.split("=");
    if (rawName && rawName.trim() === CSRF_COOKIE_NAME) {
      const value = rest.join("=").trim();
      if (value) return value;
    }
  }
  return null;
}

/**
 * Build the CSRF header object for a state-changing request.
 *
 * Returns an empty object when no token is available; callers should
 * re-bootstrap and retry rather than sending a headerless write.
 */
export function csrfHeader(): Record<string, string> {
  const token = readCsrfCookie();
  return token ? { [CSRF_HEADER]: token } : {};
}

/**
 * True when the CSRF cookie is present (the bootstrap has succeeded at
 * least once in this browser session).
 */
export function hasCsrfCookie(): boolean {
  return readCsrfCookie() !== null;
}

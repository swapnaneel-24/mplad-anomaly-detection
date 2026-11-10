// Block error panel. Shows the sanitized message and request ID from an
// ApiError. Never displays stack traces, headers, cookies or bodies.
// Optional Retry button.

import type { ReactNode } from "react";
import { ApiError } from "@/api/client";

export interface ErrorPanelProps {
  error: ApiError | Error | null;
  onRetry?: () => void;
  /** Optional title override (default: "Error"). */
  title?: string;
  /** Optional children rendered below the message (e.g. contextual help). */
  children?: ReactNode;
}

export function ErrorPanel({ error, onRetry, title = "Error", children }: ErrorPanelProps): JSX.Element | null {
  if (!error) return null;

  let message: string;
  let requestId: string | null = null;
  let code: string | null = null;

  if (error instanceof ApiError) {
    message = error.message;
    requestId = error.requestId;
    code = error.code;
  } else {
    // Defensive: a plain Error. Show the message but never a stack trace.
    message = error.message || "An unexpected error occurred.";
  }

  return (
    <section className="error-panel" role="alert" aria-live="assertive">
      <h3 className="error-panel__title">{title}</h3>
      <p className="error-panel__message">{message}</p>
      {code && (
        <p className="error-panel__meta mono">
          <span className="error-panel__meta-label">code:</span> {code}
        </p>
      )}
      {requestId && (
        <p className="error-panel__meta mono">
          <span className="error-panel__meta-label">request_id:</span> {requestId}
        </p>
      )}
      {onRetry && (
        <button type="button" className="btn btn-secondary" onClick={onRetry}>
          Retry
        </button>
      )}
      {children}
    </section>
  );
}

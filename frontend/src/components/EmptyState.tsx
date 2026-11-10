// Centered single-line empty state. Used by tables and lists when the API
// returns zero items. The message is honest ("No sources registered…"),
// never celebratory.

import type { ReactNode } from "react";

export interface EmptyStateProps {
  children: ReactNode;
}

export function EmptyState({ children }: EmptyStateProps): JSX.Element {
  return (
    <div className="empty-state" role="status">
      {children}
    </div>
  );
}

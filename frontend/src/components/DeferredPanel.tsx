// DeferredPanel: honest "Not available in this release" panel.
// Used for any functionality that is not yet implemented in PR-05A.
// Never renders greyed-out fake controls.

export interface DeferredPanelProps {
  /** Short label, e.g. "Figure 1 (deferred)" or "Case list (deferred)". */
  title: string;
  /** One-sentence description of the future intent. */
  description: string;
  /** Optional future-PR tag, e.g. "PR-05B". */
  futurePr?: string;
  /** Optional minimum height in px (default 320). */
  minHeight?: number;
}

export function DeferredPanel({
  title,
  description,
  futurePr,
  minHeight = 320,
}: DeferredPanelProps): JSX.Element {
  return (
    <section
      className="deferred-panel"
      style={{ minHeight }}
      aria-labelledby="deferred-panel-title"
    >
      <header className="deferred-panel__header">
        <span className="deferred-panel__title mono">{title}</span>
        {futurePr && <span className="deferred-panel__tag mono">{futurePr}</span>}
      </header>
      <div className="deferred-panel__body">
        <p className="deferred-panel__heading">Not available in this release</p>
        <p className="deferred-panel__description">{description}</p>
      </div>
    </section>
  );
}

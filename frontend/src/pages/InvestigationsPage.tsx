// Investigation Workspace — Evidence Casebook.
// Per SCREEN_DESIGN_NOTES.md §6. Three-column grid:
//   left (260px):   case index (deferred, empty)
//   centre (1fr):   evidence workspace (deferred)
//   right (320px):  assessment + history (deferred)
//
// The case model <dl> documents the PR-03 append-only, attributed case
// shape without faking instances.

import { DeferredPanel } from "@/components/DeferredPanel";
import { EmptyState } from "@/components/EmptyState";
import "@/pages/InvestigationsPage.css";

export function InvestigationsPage(): JSX.Element {
  return (
    <div className="investigations-page workspace-composition">
      <aside className="investigations-page__index panel" aria-label="Case index">
        <div className="panel__header">
          <span className="panel__title">Cases</span>
          <button type="button" className="btn btn-secondary btn-compact" disabled>
            New case
          </button>
        </div>
        <div className="panel__body panel__body--flush">
          <table className="data-table">
            <thead>
              <tr>
                <th scope="col">Case ID</th>
                <th scope="col">Status</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td colSpan={2}>
                  <EmptyState>No cases available. Case management is deferred to PR-05B.</EmptyState>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </aside>

      <section className="investigations-page__evidence panel" aria-label="Evidence workspace">
        <div className="panel__header">
          <span className="panel__title">Evidence</span>
        </div>
        <div className="panel__body">
          <DeferredPanel
            title="Evidence workspace (deferred)"
            description="The selected case's evidence documents, anomaly references and reviewer annotations will appear here. Cases are append-only and attributed to authenticated reviewers."
            futurePr="PR-05B"
            minHeight={220}
          />
          <h3 className="section-h4">Case model</h3>
          <dl className="def-list">
            <dt className="def-list__term">case_id</dt>
            <dd className="def-list__def mono">opaque server-issued identifier</dd>
            <dt className="def-list__term">target_ref</dt>
            <dd className="def-list__def mono">record + dataset reference</dd>
            <dt className="def-list__term">status</dt>
            <dd className="def-list__def mono">open · under_review · closed</dd>
            <dt className="def-list__term">created_by</dt>
            <dd className="def-list__def mono">user:&lt;uuid&gt; (server-derived)</dd>
            <dt className="def-list__term">actor_ref</dt>
            <dd className="def-list__def mono">user:&lt;uuid&gt; per event</dd>
            <dt className="def-list__term">version</dt>
            <dd className="def-list__def mono">optimistic-concurrency counter</dd>
            <dt className="def-list__term">events</dt>
            <dd className="def-list__def mono">append-only history</dd>
          </dl>
        </div>
      </section>

      <aside className="investigations-page__assessment panel" aria-label="Assessment and history">
        <div className="panel__header">
          <span className="panel__title">Assessment</span>
        </div>
        <div className="panel__body">
          <DeferredPanel
            title="Assessment (deferred)"
            description="Reviewer conclusions, severity assignment and disposition will appear here."
            futurePr="PR-05B"
            minHeight={140}
          />
          <DeferredPanel
            title="Event history (deferred)"
            description="The append-only case timeline (status transitions, evidence additions, reviewer comments) will appear here."
            futurePr="PR-05B"
            minHeight={140}
          />
          <h3 className="section-h4">Attribution</h3>
          <p className="editorial-muted">
            Every event carries an <code className="mono">actor_ref</code> derived
            from the authenticated principal (<code className="mono">user:&lt;uuid&gt;</code>).
            Client-supplied actor fields are never trusted.
          </p>
        </div>
      </aside>
    </div>
  );
}

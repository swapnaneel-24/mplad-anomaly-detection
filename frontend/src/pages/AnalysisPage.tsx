// Anomaly Analysis — Primary Scientific Workbench.
// Per SCREEN_DESIGN_NOTES.md §5. Four-region grid:
//   top-left (220px):    parameter rail
//   top-centre (1fr):    central analytical canvas (deferred)
//   top-right (300px):   observation inspector (deferred)
//   bottom (full width): evidence/records table (deferred, empty)
//
// The central canvas visually dominates. This is the strongest visual
// expression of the workbench (2B) design philosophy.

import { DeferredPanel } from "@/components/DeferredPanel";
import { EmptyState } from "@/components/EmptyState";
import "@/pages/AnalysisPage.css";

export function AnalysisPage(): JSX.Element {
  return (
    <div className="analysis-page workspace-composition">
      <div className="analysis-page__top">
        <aside className="analysis-page__parameters panel" aria-label="Parameters">
          <div className="panel__header">
            <span className="panel__title">Parameters</span>
            <span className="panel__title mono">PR-05B</span>
          </div>
          <div className="panel__body">
            <fieldset className="param-group" disabled>
              <legend className="param-group__legend">Detector</legend>
              <select className="param-select" defaultValue="iforest">
                <option value="iforest">Isolation Forest</option>
                <option value="lof">Local Outlier Factor</option>
                <option value="both">Both (agreement)</option>
              </select>
            </fieldset>
            <fieldset className="param-group" disabled>
              <legend className="param-group__legend">Contamination</legend>
              <input type="range" min={0} max={100} defaultValue={5} className="param-range" />
              <span className="param-value mono">0.05</span>
            </fieldset>
            <fieldset className="param-group" disabled>
              <legend className="param-group__legend">Feature subset</legend>
              <select className="param-select" defaultValue="all">
                <option value="all">all features</option>
              </select>
            </fieldset>
            <fieldset className="param-group" disabled>
              <legend className="param-group__legend">Random seed</legend>
              <input type="number" defaultValue={42} className="param-input mono" />
            </fieldset>
            <p className="param-note editorial-muted">
              Parameter sweeps will drive the central canvas once the
              research-evidence service is integrated.
            </p>
          </div>
        </aside>

        <section className="analysis-page__canvas panel" aria-label="Analytical canvas">
          <div className="panel__header">
            <span className="panel__title">Analytical canvas</span>
            <span className="panel__title mono">Figure 1 (deferred)</span>
          </div>
          <div className="analysis-page__canvas-body">
            <p className="analysis-page__canvas-heading">Analytical canvas — not yet integrated</p>
            <p className="analysis-page__canvas-desc mono">
              Coordinated anomaly-score, PCA and detector-agreement plots will
              render here for the selected dataset and parameters.
            </p>
          </div>
        </section>

        <aside className="analysis-page__inspector panel" aria-label="Observation inspector">
          <div className="panel__header">
            <span className="panel__title">Observation</span>
          </div>
          <div className="panel__body">
            <DeferredPanel
              title="Selected-observation inspector (deferred)"
              description="Feature values, anomaly score, neighbour context and reviewer notes for the selected record will appear here."
              futurePr="PR-05B"
              minHeight={180}
            />
            <h3 className="section-h4">Intended fields</h3>
            <ul className="list-clean">
              <li><span className="mono">record_id</span></li>
              <li><span className="mono">anomaly_score</span></li>
              <li><span className="mono">detector_consensus</span></li>
              <li><span className="mono">feature_contributions</span></li>
              <li><span className="mono">reviewer_note</span></li>
            </ul>
          </div>
        </aside>
      </div>

      <section className="analysis-page__records panel" aria-label="Records">
        <div className="panel__header">
          <span className="panel__title">Records</span>
          <span className="panel__title mono">0 records</span>
        </div>
        <div className="panel__body panel__body--flush">
          <p className="table-caption analysis-page__caption">
            Table 3. Anomaly records (deferred).
          </p>
          <table className="data-table">
            <thead>
              <tr>
                <th scope="col">Record ID</th>
                <th scope="col">Dataset</th>
                <th scope="col">Detector</th>
                <th scope="col">Score</th>
                <th scope="col">Rank</th>
                <th scope="col">Review status</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td colSpan={6}>
                  <EmptyState>
                    No records available. The research-evidence service is not yet integrated.
                  </EmptyState>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

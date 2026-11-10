// Context strip — workspace name + contextual breadcrumb.
//
// A single 32px-tall sticky band. The workspace name is the page H1
// (visible to assistive tech, focusable for route-change focus
// management). The breadcrumb is workspace-specific metadata in mono.

import { useEffect } from "react";
import { useLocation } from "react-router-dom";
import { findWorkspace } from "@/layout/workspaces";
import { setDocumentTitle } from "@/utils/title";
import "@/layout/ContextStrip.css";

export function ContextStrip(): JSX.Element {
  const location = useLocation();
  const ws = findWorkspace(location.pathname);
  const pageTitle = ws?.title ?? "PEIARS";
  const breadcrumb = ws?.contextBreadcrumb ?? "";

  useEffect(() => {
    setDocumentTitle(pageTitle);
  }, [pageTitle]);

  return (
    <div className="context-strip" role="navigation" aria-label="Workspace context">
      <h1
        id="workspace-heading"
        className="context-strip__title"
        tabIndex={-1}
      >
        {pageTitle}
      </h1>
      <span className="context-strip__sep" aria-hidden="true">/</span>
      <span className="context-strip__breadcrumb mono">{breadcrumb}</span>
      <div className="context-strip__actions" aria-hidden="true">
        {/* Reserved for workspace-specific contextual actions (PR-05B+). */}
      </div>
    </div>
  );
}

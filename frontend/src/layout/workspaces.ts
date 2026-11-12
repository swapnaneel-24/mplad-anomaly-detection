// Workspace metadata: the canonical list of six workspaces.
// Used by the workspace switcher (horizontal tabs), the context strip,
// and the route document-title.

export interface Workspace {
  number: string; // "01".."06"
  path: string; // "/overview", etc.
  shortTitle: string; // switcher tab label
  title: string; // context-strip H1 + document title
  /** Contextual breadcrumb shown in the context strip (mono, muted). */
  contextBreadcrumb: string;
}

export const WORKSPACES: readonly Workspace[] = [
  {
    number: "01",
    path: "/overview",
    shortTitle: "Overview",
    title: "Study Overview",
    contextBreadcrumb: "dataset: none registered / method: unsupervised (frozen)",
  },
  {
    number: "02",
    path: "/data",
    shortTitle: "Data",
    title: "Data Observatory",
    contextBreadcrumb: "dataset: source registry / records: 0",
  },
  {
    number: "03",
    path: "/analysis",
    shortTitle: "Analysis",
    title: "Anomaly Analysis",
    contextBreadcrumb: "dataset: none registered / model: Isolation Forest + LOF (deferred)",
  },
  {
    number: "04",
    path: "/investigations",
    shortTitle: "Investigations",
    title: "Investigation Workspace",
    contextBreadcrumb: "source: synthetic demonstration / cases: live",
  },
  {
    number: "05",
    path: "/domains",
    shortTitle: "Domains",
    title: "Cross-Domain Study",
    contextBreadcrumb: "comparison: ULB · PMGSY · MPLADS",
  },
  {
    number: "06",
    path: "/research",
    shortTitle: "Research",
    title: "Research & Provenance",
    contextBreadcrumb: "pipeline: frozen / backend tests: 472",
  },
] as const;

export function findWorkspace(pathname: string): Workspace | null {
  for (const ws of WORKSPACES) {
    if (pathname === ws.path || pathname.startsWith(ws.path + "/")) return ws;
  }
  return null;
}

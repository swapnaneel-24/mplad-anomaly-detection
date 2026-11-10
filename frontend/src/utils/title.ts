// Small helper to set the document title per route.
// Format: "<workspace> · PEIARS".

export function setDocumentTitle(workspace: string): void {
  if (typeof document === "undefined") return;
  document.title = `${workspace} · PEIARS`;
}

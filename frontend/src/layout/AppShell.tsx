// Desktop-only application shell — PR-05A redesign.
//
// Replaces the previous permanent-left-sidebar layout with a vertical
// stack of horizontal bands:
//   1. Identity bar (40px) — PEIARS mark + env + connectivity + user + sign out
//   2. Workspace switcher (36px) — six horizontal tabs
//   3. Context strip (32px) — workspace name + contextual breadcrumb
//   4. Workspace composition (flexible) — workspace-specific panel grid
//   5. Provenance footer (24px) — API status + version + git commit
//
// Desktop-only: when window.innerWidth < 1024 (the PR-06A minimum), the
// composition area is replaced by a DesktopGate panel. The identity bar, switcher, context
// strip, and footer remain visible (the user is still authenticated).

import { useEffect, useState } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { IdentityBar } from "@/layout/IdentityBar";
import { WorkspaceSwitcher } from "@/layout/WorkspaceSwitcher";
import { ContextStrip } from "@/layout/ContextStrip";
import { ProvenanceFooter } from "@/layout/ProvenanceFooter";
import { DesktopGate, DESKTOP_MIN_WIDTH } from "@/layout/DesktopGate";
import "@/layout/AppShell.css";

export function AppShell(): JSX.Element {
  const [desktop, setDesktop] = useState<boolean>(() => isDesktopWidth());
  const location = useLocation();

  // Re-evaluate the desktop-width gate on resize (debounced).
  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | null = null;
    const onResize = () => {
      if (timer) clearTimeout(timer);
      timer = setTimeout(() => setDesktop(isDesktopWidth()), 150);
    };
    window.addEventListener("resize", onResize);
    return () => {
      window.removeEventListener("resize", onResize);
      if (timer) clearTimeout(timer);
    };
  }, []);

  // Move focus to the main content heading on route change (accessibility).
  useEffect(() => {
    const heading = document.getElementById("workspace-heading");
    if (heading) {
      heading.focus();
    }
  }, [location.pathname]);

  return (
    <div className="app-shell" data-desktop={desktop ? "true" : "false"}>
      <IdentityBar />
      <WorkspaceSwitcher />
      <ContextStrip />
      <main className="app-shell__composition" id="main-content">
        {desktop ? <Outlet /> : <DesktopGate />}
      </main>
      <ProvenanceFooter />
    </div>
  );
}

function isDesktopWidth(): boolean {
  if (typeof window === "undefined") return true;
  return window.innerWidth >= DESKTOP_MIN_WIDTH;
}

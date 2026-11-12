// DesktopGate — shown when the viewport is narrower than 1024 CSS pixels.
//
// PR-06A contract: the minimum supported viewport width is exactly 1024
// CSS pixels (normalized from the earlier 1280 after Windows 11
// acceptance testing identified that useful laptop configurations were
// unnecessarily blocked). PEIARS remains desktop-only: there is no mobile
// layout, no hamburger, no drawer. The gate replaces only the workspace
// composition area; the identity bar, switcher, context strip, and
// provenance footer remain visible so the user can still navigate, log
// out, or see connectivity state.

import { useEffect, useState } from "react";
import "@/layout/DesktopGate.css";

/** The minimum supported viewport width (PR-06A contract). */
export const DESKTOP_MIN_WIDTH = 1024;

export function DesktopGate(): JSX.Element {
  const [width, setWidth] = useState<number>(() =>
    typeof window === "undefined" ? DESKTOP_MIN_WIDTH : window.innerWidth,
  );

  useEffect(() => {
    const onResize = () => setWidth(window.innerWidth);
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  return (
    <div className="desktop-gate" role="alert" aria-live="polite">
      <div className="desktop-gate__card">
        <h2 className="desktop-gate__title">Desktop window required</h2>
        <p className="desktop-gate__lede editorial-muted">
          PEIARS is an analytical workbench that requires a desktop-sized
          window. Widen your browser window to at least {DESKTOP_MIN_WIDTH} CSS
          pixels, or use a desktop monitor.
        </p>
        <p className="desktop-gate__width mono">
          current width: {width}px · minimum: {DESKTOP_MIN_WIDTH}px
        </p>
      </div>
    </div>
  );
}

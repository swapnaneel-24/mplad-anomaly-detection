// DesktopGate — shown when the viewport is narrower than 1280 CSS pixels.
//
// PEIARS is a desktop-only analytical workbench. The gate replaces the
// workspace composition area (not the whole shell) with a restrained
// message explaining the width requirement. The identity bar, switcher,
// context strip, and provenance footer remain visible so the user can
// still navigate, log out, or see connectivity state.

import { useEffect, useState } from "react";
import "@/layout/DesktopGate.css";

export function DesktopGate(): JSX.Element {
  const [width, setWidth] = useState<number>(() =>
    typeof window === "undefined" ? 1280 : window.innerWidth,
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
          window. Widen your browser window to at least 1280 CSS pixels, or
          use a desktop monitor.
        </p>
        <p className="desktop-gate__width mono">
          current width: {width}px · minimum: 1280px
        </p>
      </div>
    </div>
  );
}

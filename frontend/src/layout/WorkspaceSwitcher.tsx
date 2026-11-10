// Workspace switcher — compact horizontal tab list.
//
// Six tabs, one per workspace. Follows the WAI-ARIA tabs pattern:
//   - Tab to enter the tablist, Arrow Left/Right to move focus between
//     tabs, Enter/Space to activate, Tab to leave into the composition.
//   - The active tab carries aria-current="page" and the accent styling.
//
// Keyboard model:
//   - Arrow Left/Right moves *focus* (not activation) between tabs.
//   - Enter/Space activates the *focused* tab.
//   - The focused tab index is tracked separately from the active
//     (route-derived) index, so the user can move focus without
//     navigating.

import { useRef, useState, type KeyboardEvent } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { WORKSPACES } from "@/layout/workspaces";
import "@/layout/WorkspaceSwitcher.css";

export function WorkspaceSwitcher(): JSX.Element {
  const location = useLocation();
  const navigate = useNavigate();
  const tabRefs = useRef<Array<HTMLButtonElement | null>>([]);

  const activeIndex = WORKSPACES.findIndex(
    (ws) => location.pathname === ws.path || location.pathname.startsWith(ws.path + "/"),
  );
  const safeActive = activeIndex < 0 ? 0 : activeIndex;

  // The focused tab index (for roving tabindex + arrow-key navigation).
  // Initialized to the active tab; updated on Arrow Left/Right.
  const [focusedIndex, setFocusedIndex] = useState<number>(safeActive);

  const activate = (index: number): void => {
    const ws = WORKSPACES[index];
    if (!ws) return;
    setFocusedIndex(index);
    navigate(ws.path);
  };

  const focusTab = (index: number): void => {
    setFocusedIndex(index);
    tabRefs.current[index]?.focus();
  };

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>): void => {
    const tabs = WORKSPACES;
    let index = focusedIndex;
    if (event.key === "ArrowRight") {
      event.preventDefault();
      index = (focusedIndex + 1) % tabs.length;
      focusTab(index);
    } else if (event.key === "ArrowLeft") {
      event.preventDefault();
      index = (focusedIndex - 1 + tabs.length) % tabs.length;
      focusTab(index);
    } else if (event.key === "Home") {
      event.preventDefault();
      focusTab(0);
    } else if (event.key === "End") {
      event.preventDefault();
      focusTab(tabs.length - 1);
    } else if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      activate(focusedIndex);
    }
  };

  return (
    <nav className="workspace-switcher" aria-label="Workspace switcher">
      <div
        className="workspace-switcher__tablist"
        role="tablist"
        aria-label="Workspaces"
        onKeyDown={onKeyDown}
      >
        {WORKSPACES.map((ws, index) => {
          const isActive = index === safeActive;
          const isFocused = index === focusedIndex;
          return (
            <button
              key={ws.path}
              ref={(el) => { tabRefs.current[index] = el; }}
              type="button"
              role="tab"
              className={`workspace-switcher__tab ${isActive ? "is-active" : ""}`}
              aria-current={isActive ? "page" : undefined}
              aria-selected={isActive}
              // Roving tabindex: the focused tab (or the active tab when no
              // tab has been explicitly focused) is in the tab order.
              tabIndex={isFocused ? 0 : -1}
              onClick={() => activate(index)}
              title={ws.title}
            >
              <span className="workspace-switcher__tab-number mono">{ws.number}</span>
              <span className="workspace-switcher__tab-label">{ws.shortTitle}</span>
            </button>
          );
        })}
      </div>
    </nav>
  );
}

import { useState, useEffect } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { env } from "@/lib/env";
import JudgeTourModal from "@/components/shell/JudgeTourModal";

/**
 * App chrome. The foundation (vercel-brand.css) scopes typography and themes
 * under .vbg-report; app-owned zt-* classes read only public tokens.
 * The rail exists at ≥900px; below that the topbar is the navigator.
 */
export default function AppShell() {
  const [tourOpen, setTourOpen] = useState(false);

  return (
    <div className="vbg-report">
      <div className="zt-shell">
        <aside className="zt-rail">
          <div className="zt-rail-brand">
            <span className="zt-rail-brandmark" aria-hidden="true">
              ZT
            </span>
            <span className="zt-rail-name">ZeroTrace</span>
            <span className="zt-meta">{env.envLabel}</span>
          </div>

          <nav className="zt-rail-section" aria-label="Workflows">
            <p className="zt-rail-heading">Workflows</p>
            <NavLink to="/" end className="zt-rail-link">
              <span>Overview</span>
            </NavLink>
            <NavLink to="/portal" className="zt-rail-link">
              <span>Data Principal Portal</span>
            </NavLink>
            <NavLink to="/console" end className="zt-rail-link">
              <span>DPO Console</span>
            </NavLink>
            <NavLink to="/console/impact" className="zt-rail-link">
              <span>Impact</span>
            </NavLink>
            <NavLink to="/console/policies" className="zt-rail-link">
              <span>Policies</span>
            </NavLink>
            <NavLink to="/adversary" className="zt-rail-link">
              <span>Adversary Console</span>
            </NavLink>
            <NavLink to="/verify" className="zt-rail-link">
              <span>Public Verifier</span>
            </NavLink>
          </nav>

          <nav className="zt-rail-section" aria-label="Presenter">
            <p className="zt-rail-heading">Presenter</p>
            <NavLink to="/demo" className="zt-rail-link">
              <span>Demo Director</span>
            </NavLink>
            <button
              type="button"
              className="zt-tour-trigger-btn"
              style={{ width: "100%", justifyContent: "center", marginTop: "1rem" }}
              onClick={() => setTourOpen(true)}
            >
              <span className="zt-tour-trigger-beacon" aria-hidden="true" />
              <span>⚡ Evaluator Guide</span>
            </button>
          </nav>

          <div className="zt-rail-footer">
            <p className="zt-caption">
              Erasure and proof infrastructure for DPDP Act compliance. All statutory mappings
              require legal review.
            </p>
          </div>
        </aside>

        <div className="zt-body">
          <header className="zt-topbar">
            <a className="zt-skip" href="#content">
              Skip to content
            </a>
            <span className="zt-topbar-title">ZeroTrace</span>
            <span className="zt-topbar-context">Kaveri Finserv (ap-south-1)</span>
            <span className="zt-topbar-env" data-tone="neutral">
              {env.envLabel}
            </span>

            <button
              type="button"
              className="zt-tour-trigger-btn"
              onClick={() => setTourOpen(true)}
              title="Open Technical Architecture Evaluation Guide"
            >
              <span className="zt-tour-trigger-beacon" aria-hidden="true" />
              <span>⚡ Technical Runbook</span>
            </button>
          </header>
          <main className="zt-main" id="content">
            <Outlet />
          </main>
        </div>
      </div>

      <JudgeTourModal open={tourOpen} onClose={() => setTourOpen(false)} />
    </div>
  );
}

export function useDocumentTitle(title: string): void {
  const loc = useLocation();
  useEffect(() => {
    document.title = `${title} · ZeroTrace`;
    void loc; // route changes re-run the effect
  }, [title, loc]);
}

import { lazy, Suspense } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import AppShell from "@/components/shell/AppShell";
import { SkeletonRows } from "@/components/ui/States";
import LandingPage from "@/routes/LandingPage";
import ConsoleQueuePage from "@/routes/ConsoleQueuePage";

/* The job screen carries the lineage graph stack (xyflow + dagre) and the
   virtualized log; keep it out of the entry chunk. */
const JobDetailPage = lazy(() => import("@/routes/JobDetailPage"));
const PortalPage = lazy(() => import("@/routes/PortalPage"));
const AdversaryPage = lazy(() => import("@/routes/AdversaryPage"));
const VerifierPage = lazy(() => import("@/routes/VerifierPage"));
const DemoDirectorPage = lazy(() => import("@/routes/DemoDirectorPage"));
const ImpactPage = lazy(() => import("@/routes/ImpactPage"));
const PoliciesPage = lazy(() => import("@/routes/PoliciesPage"));
const NotFoundPage = lazy(() => import("@/routes/NotFoundPage"));

function RouteSuspense({ children }: { children: React.ReactNode }) {
  return (
    <Suspense
      fallback={
        <div className="zt-stack-page" aria-busy="true">
          <p className="vbg-label">Loading section…</p>
          <SkeletonRows rows={4} />
        </div>
      }
    >
      {children}
    </Suspense>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppShell />}>
          <Route path="/" element={<LandingPage />} />
          <Route path="/portal" element={<RouteSuspense><PortalPage /></RouteSuspense>} />
          <Route path="/console" element={<ConsoleQueuePage />} />
          <Route
            path="/console/jobs/:jobId"
            element={<RouteSuspense><JobDetailPage /></RouteSuspense>}
          />
          <Route path="/console/impact" element={<RouteSuspense><ImpactPage /></RouteSuspense>} />
          <Route path="/console/policies" element={<RouteSuspense><PoliciesPage /></RouteSuspense>} />
          <Route path="/adversary" element={<RouteSuspense><AdversaryPage /></RouteSuspense>} />
          <Route path="/verify" element={<RouteSuspense><VerifierPage /></RouteSuspense>} />
          <Route path="/verify/:receiptId" element={<RouteSuspense><VerifierPage /></RouteSuspense>} />
          <Route path="/demo" element={<RouteSuspense><DemoDirectorPage /></RouteSuspense>} />
          <Route path="/404" element={<RouteSuspense><NotFoundPage /></RouteSuspense>} />
          <Route path="*" element={<Navigate to="/404" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

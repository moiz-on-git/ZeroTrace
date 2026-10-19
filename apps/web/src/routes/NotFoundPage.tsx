import { Link } from "react-router-dom";
import { useDocumentTitle } from "@/components/shell/AppShell";

export default function NotFoundPage() {
  useDocumentTitle("Not found");
  return (
    <div className="zt-stack-page">
      <header className="zt-page-head">
        <h1 className="vbg-title">404 · no such page</h1>
        <p className="zt-lede">The path does not exist on this deployment. Nothing was erased, nothing was buried.</p>
      </header>
      <p className="zt-copy">
        <Link to="/">Overview</Link> · <Link to="/console">DPO console</Link> · <Link to="/verify">Public verifier</Link>
      </p>
    </div>
  );
}

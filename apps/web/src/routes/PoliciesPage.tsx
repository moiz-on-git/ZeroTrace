import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";
import { policiesZ, type Policies } from "@/api/schemas";
import { SectionHeading } from "@/components/ui/SectionHeading";
import { Chip } from "@/components/ui/Chip";
import { ErrorState, SkeletonRows } from "@/components/ui/States";
import { useDocumentTitle } from "@/components/shell/AppShell";

export default function PoliciesPage() {
  useDocumentTitle("Policies");

  const query = useQuery({
    queryKey: ["policies"],
    queryFn: () => api.get("/api/v1/policies", policiesZ),
  });

  const policies = query.data as Policies | undefined;

  return (
    <div className="zt-stack-page">
      <header className="zt-page-head">
        <div>
          <h1 className="vbg-title">Retention & Erasure Policies</h1>
          <p className="zt-lede">
            Configurable regulatory rulebook mapping DPDP Act 2023, PMLA 2002, and RBI Master Directions into
            deterministic data plane actions.
          </p>
        </div>
        {policies ? (
          <div className="zt-landing-context-list" style={{ marginTop: "var(--vbg-space-2)" }}>
            <span className="zt-meta">Rulebook: <strong className="zt-id">{policies.rulebook}</strong></span>
            <span className="zt-meta">Version: <strong className="zt-id">{policies.policy_version}</strong></span>
            <Chip tone="warning">requires legal review</Chip>
          </div>
        ) : null}
      </header>

      {query.isPending ? <SkeletonRows rows={4} /> : null}

      {query.isError ? (
        <ErrorState
          title="Policies unavailable"
          body="Could not load the regulatory retention policy rulebook."
          retry={() => query.refetch()}
        />
      ) : null}

      {policies ? (
        <>
          <section>
            <SectionHeading
              title="Statutory taxonomy rules"
              hint="Rules determining whether data categories are immediately purged or securely held until statutory expiry."
            />
            <table className="zt-portal-table">
              <thead>
                <tr>
                  <th>Category</th>
                  <th>Action</th>
                  <th>Statutory retention</th>
                  <th>Legal basis & citation</th>
                  <th>Notes</th>
                </tr>
              </thead>
              <tbody>
                {policies.rules.map((rule) => (
                  <tr key={rule.category}>
                    <td>
                      <code className="zt-id">{rule.category}</code>
                    </td>
                    <td>
                      <Chip tone={rule.action === "ERASE_NOW" ? "success" : "warning"}>
                        {rule.action.replace(/_/g, " ").toLowerCase()}
                      </Chip>
                    </td>
                    <td className="zt-num">{rule.retention}</td>
                    <td>
                      <div style={{ display: "grid", gap: "2px" }}>
                        <span>{rule.citation}</span>
                        {rule.legal_review_required ? (
                          <span style={{ color: "var(--vbg-color-warning)", fontSize: "var(--vbg-type-metadata)" }}>
                            * Requires independent legal review
                          </span>
                        ) : null}
                      </div>
                    </td>
                    <td className="zt-copy">{rule.note}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          <section>
            <SectionHeading
              title="Legal Disclaimer"
              hint="Statutory mappings must be validated against organizational regulatory counsel."
            />
            <p className="zt-copy">
              ZeroTrace enforces cryptographic isolation, targeted deletion, and verifiable proof anchoring.
              The retention periods and legal basis citations defined in this policy configuration represent reference
              templates for standard Indian Non-Banking Financial Companies (NBFCs) and must be reviewed by
              designated compliance officers and legal counsel prior to production enforcement.
            </p>
          </section>
        </>
      ) : null}
    </div>
  );
}

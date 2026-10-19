import { useEffect, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Background,
  Controls,
  Handle,
  Position,
  ReactFlow,
  ReactFlowProvider,
  useReactFlow,
} from "@xyflow/react";
import type { Edge, Node } from "@xyflow/react";
import dagre from "@dagrejs/dagre";
import "@xyflow/react/dist/style.css";
import { api } from "@/api/client";
import { lineageZ, type Lineage } from "@/api/schemas";
import { SectionHeading } from "@/components/ui/SectionHeading";
import { ErrorState, SkeletonRows } from "@/components/ui/States";
import { Chip } from "@/components/ui/Chip";
import { jobStreamStore } from "@/hooks/useJobEvents";
import { formatCount } from "@/lib/format";

const NODE_W = 210;
const NODE_H = 58;

type ZtNodeData = {
  label: string;
  resource: string;
  decision: "erase" | "hold" | "pending";
  category: string;
};
type ZtFlowNode = Node<ZtNodeData, "zt" | "ztSubject">;

function layoutGraph(raw: Lineage, revealed: ReadonlySet<string>): { nodes: ZtFlowNode[]; edges: Edge[] } {
  const shown = raw.nodes.filter((n) => n.type === "subject" || revealed.has(n.id));
  const g = new dagre.graphlib.Graph();
  g.setGraph({ rankdir: "LR", nodesep: 22, ranksep: 104, marginx: 16, marginy: 16 });
  g.setDefaultEdgeLabel(() => ({}));
  for (const n of shown) g.setNode(n.id, { width: NODE_W, height: NODE_H });
  for (const e of raw.edges) {
    const both = shown.some((n) => n.id === e.source) && shown.some((n) => n.id === e.target);
    if (both) g.setEdge(e.source, e.target);
  }
  dagre.layout(g);

  const nodes: ZtFlowNode[] = shown.map((n) => {
    const p = g.node(n.id);
    return {
      id: n.id,
      type: n.type === "subject" ? "ztSubject" : "zt",
      position: { x: p.x - NODE_W / 2, y: p.y - NODE_H / 2 },
      draggable: false,
      data: { label: n.label, resource: n.resource, decision: n.decision, category: n.data_category },
    };
  });
  const edges: Edge[] = raw.edges
    .filter((e) => shown.some((n) => n.id === e.source) && shown.some((n) => n.id === e.target))
    .map((e) => ({ id: `${e.source}->${e.target}`, source: e.source, target: e.target, label: e.label || undefined }));
  return { nodes, edges };
}

function ZtFlowNodeView({ data }: { data: ZtNodeData }) {
  return (
    <div className="zt-flow-node" data-decision={data.decision}>
      <Handle type="target" position={Position.Left} isConnectable={false} />
      <span className="zt-flow-cat">{data.category}</span>
      <span className="zt-flow-label">{data.label}</span>
      <span className="zt-flow-res">{data.resource}</span>
      <span className="zt-flow-decision" data-decision={data.decision}>
        {data.decision}
      </span>
      <Handle type="source" position={Position.Right} isConnectable={false} />
    </div>
  );
}

function ZtSubjectNodeView({ data }: { data: ZtNodeData }) {
  return (
    <div className="zt-flow-node zt-flow-subject" data-decision={data.decision}>
      <Handle type="source" position={Position.Right} isConnectable={false} />
      <span className="zt-flow-cat">{data.category}</span>
      <span className="zt-flow-label">{data.label}</span>
      <span className="zt-flow-res">{data.resource}</span>
    </div>
  );
}

const nodeTypes = { zt: ZtFlowNodeView, ztSubject: ZtSubjectNodeView };

/** (c) Lineage graph. Nodes appear one at a time as the DISCOVERY loop reports
 *  them; edges join once both ends exist. dagre layout, engineering look. */
export default function LineageSection({ jobId }: { jobId: string }) {
  return (
    <ReactFlowProvider>
      <LineageFlow jobId={jobId} />
    </ReactFlowProvider>
  );
}

function LineageFlow({ jobId }: { jobId: string }) {
  const lineage = useQuery({
    queryKey: ["lineage", jobId],
    queryFn: () => api.get(`/api/v1/jobs/${encodeURIComponent(jobId)}/lineage`, lineageZ),
  });
  const revealedNodes = jobStreamStore((s) => s.view.revealedNodes);
  const discoveryRunning = jobStreamStore((s) => s.view.stages.DISCOVERY.status);
  const streamEnded = jobStreamStore((s) => Boolean(s.view.finalStatus));

  const raw = (lineage.data ?? null) as Lineage | null;
  const rf = useReactFlow();

  const revealedSet = useMemo(() => new Set(revealedNodes), [revealedNodes]);
  const revealSignature = useMemo(() => revealedNodes.join("|"), [revealedNodes]);

  /* Layout derives during render: nodes appear one at a time as the DISCOVERY
     loop reports them; once the stream is done the full graph is honest, even
     for pages opened mid-run that missed the DISCOVERY events. dagre runs on a
     handful of nodes — cheap enough to skip effect-driven state entirely. */
  const laid = useMemo(() => {
    if (!raw) return { nodes: [] as ZtFlowNode[], edges: [] as Edge[] };
    if (revealSignature.length > 0) return layoutGraph(raw, revealedSet);
    if (streamEnded) return layoutGraph(raw, new Set(raw.nodes.map((n) => n.id)));
    return { nodes: [] as ZtFlowNode[], edges: [] as Edge[] };
  }, [raw, revealSignature, revealedSet, streamEnded]);

  /* recentre only when the layout shape changes — an external-system call */
  useEffect(() => {
    if (laid.nodes.length === 0) return;
    const t = window.setTimeout(() => void rf.fitView({ padding: 0.12, duration: 140 }), 40);
    return () => window.clearTimeout(t);
  }, [laid, rf]);

  const holdCount = laid.nodes.filter((n) => n.data.decision === "hold").length;
  const eraseCount = laid.nodes.filter((n) => n.data.decision === "erase").length;

  return (
    <section className="zt-job-section" id="lineage">
      <SectionHeading
        title="Lineage"
        hint={
          discoveryRunning === "pending" && revealedNodes.length === 0
            ? "The graph builds as discovery reports locations."
            : `${formatCount(eraseCount)} location${eraseCount === 1 ? "" : "s"} to erase · ${formatCount(holdCount)} on lawful hold · ${discoveryRunning === "running" ? "discovering…" : "discovery complete"}`
        }
        trailing={<Chip tone="neutral">{`${laid.nodes.length} nodes`}</Chip>}
      />

      {lineage.isPending ? (
        <SkeletonRows rows={3} />
      ) : lineage.isError ? (
        <ErrorState title="Lineage unavailable" retry={() => lineage.refetch()} />
      ) : (
        <div className="zt-lineage-wrap" role="img" aria-label="Lineage graph of the subject's data locations">
          <ReactFlow
            nodes={laid.nodes}
            edges={laid.edges}
            nodeTypes={nodeTypes}
            nodesConnectable={false}
            nodesDraggable={false}
            minZoom={0.3}
            maxZoom={1.5}
            colorMode="system"
          >
            <Background gap={14} size={1} />
            <Controls showInteractive={false} />
          </ReactFlow>
        </div>
      )}
    </section>
  );
}

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { ErrorBox, Icon, Loading, Price } from "../components/ui";
import type { Product } from "../types";

type N = { id: number; kind: string; title: string; body: string; read: boolean; created_at: string; product: Product | null };
const ICON: Record<string, string> = { price_drop: "tag", restock: "bolt", new_arrival: "sparkle", order: "bag" };

export default function Notifications() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["notifications"], queryFn: () => api.get<N[]>("/notifications"), refetchInterval: 5000 });
  const read = useMutation({ mutationFn: () => api.post("/notifications/read"), onSuccess: () => qc.invalidateQueries({ queryKey: ["me"] }) });
  useEffect(() => {
    if (q.data?.some((n) => !n.read)) read.mutate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q.data]);
  if (q.error) return <ErrorBox error={q.error} onRetry={() => q.refetch()} />;
  if (!q.data) return <Loading />;
  return (
    <div style={{ maxWidth: 720, margin: "0 auto" }}>
      <span className="eyebrow">Your stylist agent</span>
      <h1>Notifications</h1>
      <p className="muted">Price drops and restocks on pieces you've hung, and new arrivals that fit your taste.</p>
      {q.data.length === 0 && <div className="empty"><h3>Nothing yet</h3><p className="muted" style={{ margin: 0 }}>We'll tell you when something you saved changes.</p></div>}
      <div className="stack">
        {q.data.map((n) => (
          <article key={n.id} className="card pad row" style={{ flexWrap: "nowrap", alignItems: "flex-start", borderColor: n.read ? undefined : "var(--sage)" }}>
            {n.product ? (
              <img src={n.product.image_url} alt="" style={{ width: 64, height: 64, objectFit: "contain", background: "#f4efe8", borderRadius: 10, flex: "none" }} />
            ) : (
              <span className="icon-btn" style={{ background: "var(--surface-2)", flex: "none" }}><Icon name={ICON[n.kind] ?? "bell"} /></span>
            )}
            <div style={{ flex: 1, minWidth: 0 }}>
              <div className="row" style={{ gap: 6 }}>
                <b>{n.title}</b>
                {!n.read && <span className="chip chip-sage">New</span>}
              </div>
              <div className="small muted">{n.body}</div>
              {n.product && <div className="row small" style={{ marginTop: 6 }}><Price price={n.product.price_inr} mrp={n.product.mrp_inr} /></div>}
            </div>
            <span className="small muted" style={{ whiteSpace: "nowrap" }}>{new Date(n.created_at + "Z").toLocaleDateString()}</span>
          </article>
        ))}
      </div>
      <div className="section"><Link to="/" className="btn">Back to wardrobes</Link></div>
    </div>
  );
}

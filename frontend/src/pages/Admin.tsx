import { useQueryClient } from "@tanstack/react-query";
import { FormEvent, useState } from "react";
import { adminToken, setAdminToken } from "../api";
import Demo from "./Demo";
import Retailer from "./Retailer";

/** Brand-side tools (not linked from the customer app): insights and simulated store events. */
export default function Admin() {
  const qc = useQueryClient();
  const [token, setToken] = useState(adminToken() ?? "");
  const [tab, setTab] = useState<"insights" | "events">("insights");
  const save = (e: FormEvent) => { e.preventDefault(); setAdminToken(token.trim() || null); qc.invalidateQueries(); };
  return (
    <>
      <span className="eyebrow">Urban Thread · brand admin</span>
      <h1>Store insights & events</h1>
      <p className="small muted">For the brand team only. Shoppers never see this page.</p>
      <form className="row" onSubmit={save} style={{ margin: "12px 0" }}>
        <label htmlFor="adm" className="small muted">Admin token</label>
        <input id="adm" className="input" type="password" style={{ maxWidth: 260, minHeight: 36 }} value={token}
          onChange={(e) => setToken(e.target.value)} placeholder="Not needed locally" />
        <button className="btn btn-sm">Use token</button>
      </form>
      <div className="tabs" role="tablist">
        <button role="tab" aria-selected={tab === "insights"} onClick={() => setTab("insights")}>Insights</button>
        <button role="tab" aria-selected={tab === "events"} onClick={() => setTab("events")}>Store events</button>
      </div>
      {tab === "insights" ? <Retailer /> : <Demo />}
    </>
  );
}

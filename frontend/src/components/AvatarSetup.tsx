import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, pretty } from "../api";
import { useVocab } from "./Layout";
import MannequinStage, { Avatar, useMannequin } from "./Mannequin";
import { ErrorBox, Icon, Modal, useToast } from "./ui";

export default function AvatarSetup({ initial, onClose }: { initial: Avatar; onClose: () => void }) {
  const qc = useQueryClient();
  const toast = useToast();
  const vocab = useVocab();
  const [a, setA] = useState<Avatar>(initial);
  const [text, setText] = useState("");
  const geo = useMannequin(a);
  const set = <K extends keyof Avatar>(k: K, v: Avatar[K]) => setA((cur) => ({ ...cur, [k]: v }));
  const describe = useMutation({
    mutationFn: () => api.post<Avatar & { source: string }>("/avatar/describe", { text, presentation: a.presentation }),
    onSuccess: (d) => { const { source: _s, ...rest } = d; void _s; setA(rest); toast("Filled in from your description. Adjust anything."); },
  });
  const save = useMutation({
    mutationFn: () => api.put<Avatar>("/avatar", a),
    onSuccess: (d) => { qc.setQueryData(["avatar"], d); toast("Mannequin updated"); onClose(); },
  });
  const v = vocab.data?.avatar;
  const types = v?.body_types[a.presentation] ?? [];

  return (
    <Modal title="Your mannequin" onClose={onClose}>
      <div className="stack">
        <p className="small muted" style={{ margin: 0 }}>
          Optional. We only use this to draw a faceless mannequin so pieces sit on a body like yours. Nothing here affects prices or matches.
        </p>
        <div style={{ display: "grid", gridTemplateColumns: "130px 1fr", gap: 14, alignItems: "start" }}>
          <MannequinStage geo={geo.data} placed={[]} dragging={false} compact />
          <div className="stack" style={{ gap: 10 }}>
            <div className="chips" role="group" aria-label="Mannequin">
              {(["women", "men"] as const).map((p) => (
                <button key={p} className="chip" aria-pressed={a.presentation === p}
                  onClick={() => setA({ ...a, presentation: p, body_type: v?.body_types[p][0] ?? "slim", hair_style: p === "men" ? "short" : a.hair_style })}>
                  {p === "women" ? "Women's" : "Men's"}
                </button>
              ))}
            </div>
            <div className="field"><span className="label">Body type</span>
              <div className="chips">{types.map((t) => <button key={t} className="chip" aria-pressed={a.body_type === t} onClick={() => set("body_type", t)}>{pretty(t)}</button>)}</div>
            </div>
            <div className="field"><span className="label">Height</span>
              <div className="chips">{v?.height_bands.map((h) => <button key={h} className="chip" aria-pressed={a.height_band === h} onClick={() => set("height_band", h)}>{pretty(h)}</button>)}</div>
            </div>
          </div>
        </div>
        <div className="field"><span className="label">Skin tone</span>
          <div className="row" style={{ gap: 6 }} role="radiogroup" aria-label="Skin tone">
            {v?.skin_tones.map((hex, i) => (
              <button key={hex} role="radio" aria-checked={a.skin_tone === i} aria-label={`Skin tone ${i + 1} of 10`} onClick={() => set("skin_tone", i)}
                style={{ width: 30, height: 30, borderRadius: 99, background: hex, cursor: "pointer",
                  border: a.skin_tone === i ? "3px solid var(--ink)" : "1px solid rgba(0,0,0,.15)" }} />
            ))}
          </div>
        </div>
        <div className="row" style={{ alignItems: "flex-start", gap: 16 }}>
          <div className="field"><span className="label">Hair</span>
            <div className="chips">{v?.hair_styles.map((h) => <button key={h} className="chip" aria-pressed={a.hair_style === h} onClick={() => set("hair_style", h)}>{pretty(h)}</button>)}</div>
          </div>
          <div className="field"><span className="label">Hair colour</span>
            <div className="row" style={{ gap: 6 }}>
              {v && Object.entries(v.hair_colors).map(([k, hex]) => (
                <button key={k} aria-label={pretty(k)} aria-pressed={a.hair_color === k} onClick={() => set("hair_color", k)}
                  style={{ width: 26, height: 26, borderRadius: 99, background: hex, cursor: "pointer", border: a.hair_color === k ? "3px solid var(--sage)" : "1px solid rgba(0,0,0,.2)" }} />
              ))}
            </div>
          </div>
        </div>
        <div className="field">
          <label htmlFor="describe">Or describe yourself <span className="muted">(optional)</span></label>
          <div className="row" style={{ flexWrap: "nowrap" }}>
            <input id="describe" className="input" value={text} onChange={(e) => setText(e.target.value)} maxLength={400}
              placeholder="e.g. 5'4, pear-shaped, wheatish, long wavy black hair" />
            <button className="btn" disabled={text.trim().length < 3 || describe.isPending} onClick={() => describe.mutate()}>
              {describe.isPending ? <span className="spinner" /> : <Icon name="sparkle" size={16} />} Fill in
            </button>
          </div>
        </div>
        {(describe.error || save.error) && <ErrorBox error={describe.error || save.error} />}
        <button className="btn btn-primary" onClick={() => save.mutate()} disabled={save.isPending}><Icon name="check" /> Save mannequin</button>
      </div>
    </Modal>
  );
}

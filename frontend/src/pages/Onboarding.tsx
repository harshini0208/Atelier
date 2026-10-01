import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, setCurrentUserId } from "../api";
import { useVocab } from "../components/Layout";
import { AboutYou, Budgets, ColoursAndOccasions, DEFAULT_DRAFT, Draft, Materials, prefsPayload, SizeAndFit } from "../components/PrefsForm";
import { ErrorBox, Icon, Loading } from "../components/ui";

const STEPS = [
  { title: "Welcome to your walk-in wardrobe", hint: "Everything you buy, bag and love at Urban Thread on one rail, ready to hang in folders and style." },
  { title: "Your sizes and fit", hint: "We'll pre-select your size and tell you when it's sold out." },
  { title: "What you like to spend", hint: "Per piece. It's a guide, not a filter." },
  { title: "Fabrics", hint: "We'll put what you love first and flag what you avoid." },
  { title: "Colours and occasions", hint: "Almost done." },
];

export default function Onboarding() {
  const vocab = useVocab();
  const nav = useNavigate();
  const qc = useQueryClient();
  const [step, setStep] = useState(0);
  const [d, setD] = useState<Draft>(DEFAULT_DRAFT);
  const [member, setMember] = useState(true);
  const create = useMutation({
    mutationFn: async () => {
      const r = await api.post<{ id: string }>("/profile", { ...prefsPayload(d), name: d.name.trim() });
      setCurrentUserId(r.id);
      if (member) await api.post("/membership/link", {}).catch(() => undefined);   // optional; never blocks sign-up
      return r;
    },
    onSuccess: (r) => { setCurrentUserId(r.id); qc.clear(); nav("/", { replace: true }); },
  });
  if (!vocab.data) return <Loading />;
  const v = vocab.data;
  const canNext = step !== 0 || d.name.trim().length > 0;
  const last = step === STEPS.length - 1;
  const body = [
    <AboutYou key="a" d={d} set={setD} vocab={v} />, <SizeAndFit key="s" d={d} set={setD} vocab={v} />,
    <Budgets key="b" d={d} set={setD} />, <Materials key="m" d={d} set={setD} vocab={v} />,
    <ColoursAndOccasions key="c" d={d} set={setD} vocab={v} />,
  ][step];

  return (
    <div style={{ maxWidth: 620, margin: "0 auto" }}>
      <div className="row" style={{ gap: 6, marginBottom: 18 }} aria-label={`Step ${step + 1} of ${STEPS.length}`}>
        {STEPS.map((_, i) => <span key={i} style={{ flex: 1, height: 4, borderRadius: 4, background: i <= step ? "var(--ink)" : "var(--line)" }} />)}
      </div>
      <span className="eyebrow">Step {step + 1} of {STEPS.length}</span>
      <h1>{step === 0 ? STEPS[0].title : step === 1 && d.name ? `Nice to meet you, ${d.name.trim().split(" ")[0]}.` : STEPS[step].title}</h1>
      <p className="muted">{STEPS[step].hint}</p>
      <form className="card pad stack" onSubmit={(e) => { e.preventDefault(); if (!canNext) return; if (last) create.mutate(); else setStep(step + 1); }}>
        {body}
        {last && (
          <label className="folder-check" style={{ alignItems: "flex-start" }}>
            <input type="checkbox" checked={member} onChange={(e) => setMember(e.target.checked)} style={{ marginTop: 2 }} />
            <span>
              <b>Bring in my Urban Thread purchases</b>
              <span className="small muted" style={{ display: "block" }}>Link your membership so pieces you bought online and in store
                show on your rail. <i>Demo: a sample purchase history is added.</i></span>
            </span>
          </label>
        )}
        {create.error && <ErrorBox error={create.error} />}
        <div className="row-between" style={{ marginTop: 8 }}>
          {step > 0 ? <button type="button" className="btn btn-ghost" onClick={() => setStep(step - 1)}><Icon name="back" size={16} /> Back</button> : <span />}
          <div className="row">
            {step > 0 && !last && <button type="button" className="btn btn-ghost" onClick={() => setStep(step + 1)}>Skip</button>}
            <button className="btn btn-primary" disabled={!canNext || create.isPending}>
              {create.isPending ? <span className="spinner" /> : null}{last ? "Start my wardrobe" : "Next"} <Icon name="arrow" size={16} />
            </button>
          </div>
        </div>
      </form>
      <p className="small muted" style={{ textAlign: "center", marginTop: 12 }}>You can change any of this later in Preferences.</p>
    </div>
  );
}

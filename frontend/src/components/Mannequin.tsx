import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import { ErrorBox, useToast } from "./ui";

export const BODY_TYPES = [
  { key: "slim", label: "Slim" }, { key: "curvy", label: "Curvy" }, { key: "plus", label: "Plus size" }, { key: "athletic", label: "Athletic" },
];
export const SKIN_TONES = [
  { key: "light", label: "Light", hex: "#e9d6bf" }, { key: "tan", label: "Tan", hex: "#cfa57c" },
  { key: "brown", label: "Brown", hex: "#9a6a47" }, { key: "deep", label: "Deep", hex: "#5d3e2c" },
];
export type MannequinChoice = { body_type: string; skin_tone: string; chosen?: boolean };
export const mannequinUrl = (m: MannequinChoice) => `/api/mannequins/${m.body_type}-${m.skin_tone}.png`;

export const useMannequin = () => useQuery({ queryKey: ["mannequin"], queryFn: () => api.get<MannequinChoice>("/mannequin") });

/** Body type x finish. The mannequin your looks are dressed on, so you can see how pieces fit a body like yours. */
export function MannequinPicker({ value, onChange }: { value: MannequinChoice; onChange: (m: MannequinChoice) => void }) {
  return (
    <div className="mq-picker">
      <img className="mq-preview" src={mannequinUrl(value)} alt={`${value.body_type} mannequin, ${value.skin_tone} finish`} />
      <div className="stack" style={{ gap: 14 }}>
        <div className="field">
          <span className="label">Body type</span>
          <div className="mq-bodies" role="radiogroup" aria-label="Body type">
            {BODY_TYPES.map((b) => (
              <button type="button" key={b.key} role="radio" aria-checked={value.body_type === b.key}
                className={`mq-body ${value.body_type === b.key ? "on" : ""}`} onClick={() => onChange({ ...value, body_type: b.key })}>
                <img src={mannequinUrl({ body_type: b.key, skin_tone: value.skin_tone })} alt="" />
                <span>{b.label}</span>
              </button>
            ))}
          </div>
        </div>
        <div className="field">
          <span className="label">Finish</span>
          <div className="row" style={{ gap: 10 }} role="radiogroup" aria-label="Finish">
            {SKIN_TONES.map((t) => (
              <button type="button" key={t.key} role="radio" aria-checked={value.skin_tone === t.key} aria-label={t.label} title={t.label}
                className={`mq-tone ${value.skin_tone === t.key ? "on" : ""}`} style={{ background: t.hex }}
                onClick={() => onChange({ ...value, skin_tone: t.key })} />
            ))}
          </div>
        </div>
        <span className="small muted">Only used to show how pieces drape and fit. The mannequin is faceless; no photos of you.</span>
      </div>
    </div>
  );
}

/** Preferences: change the mannequin (saves straight away). */
export function MannequinSection() {
  const qc = useQueryClient();
  const toast = useToast();
  const q = useMannequin();
  const save = useMutation({
    mutationFn: (m: MannequinChoice) => api.put<MannequinChoice>("/mannequin", m),
    onMutate: (m) => qc.setQueryData(["mannequin"], m),
    onSuccess: (m) => { qc.setQueryData(["mannequin"], m); toast("Mannequin updated. Looks will be dressed on it."); },
  });
  if (q.error) return <ErrorBox error={q.error} />;
  if (!q.data) return null;
  return (
    <>
      <MannequinPicker value={q.data} onChange={(m) => save.mutate(m)} />
      {save.error && <ErrorBox error={save.error} />}
    </>
  );
}

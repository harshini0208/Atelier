import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { api } from "../api";
import { useMe, useVocab } from "../components/Layout";
import { MannequinSection } from "../components/Mannequin";
import { AboutYou, Budgets, ColoursAndOccasions, Draft, Materials, prefsPayload, SizeAndFit } from "../components/PrefsForm";
import { ErrorBox, Icon, Loading, useToast } from "../components/ui";
import type { Preferences as Prefs } from "../types";

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return <section className="card pad stack"><h3>{title}</h3>{children}</section>;
}

export default function Preferences() {
  const qc = useQueryClient();
  const toast = useToast();
  const vocab = useVocab();
  const me = useMe();
  const q = useQuery({ queryKey: ["prefs"], queryFn: () => api.get<Prefs>("/preferences") });
  const [d, setD] = useState<Draft | null>(null);
  useEffect(() => { if (q.data && me.data) setD({ ...q.data, name: me.data.name }); }, [q.data, me.data]);
  const save = useMutation({
    mutationFn: async (body: Draft) => {
      await api.patch("/me", { name: body.name.trim(), city: body.city });
      return api.put<Prefs>("/preferences", prefsPayload(body));
    },
    onSuccess: (p) => {
      qc.setQueryData(["prefs"], p);
      ["me", "folder", "matches", "piece-matches", "shop"].forEach((k) => qc.invalidateQueries({ queryKey: [k] }));
      toast("Saved. Your matches are updated.");
    },
  });
  if (q.error) return <ErrorBox error={q.error} onRetry={() => q.refetch()} />;
  if (!d || !vocab.data) return <Loading label="Loading your preferences" />;
  const v = vocab.data;
  return (
    <form onSubmit={(e) => { e.preventDefault(); if (d.name.trim()) save.mutate(d); }}>
      <span className="eyebrow">Your profile</span>
      <h1>Preferences</h1>
      <p className="muted" style={{ marginTop: 4 }}>
        These are soft preferences. Matches that fit them show under <b>For you</b>; great matches that don't are still shown
        under <b>Also view</b>, with the reason.
      </p>
      <div className="prefs-grid section">
        <Section title="About you"><AboutYou d={d} set={setD} vocab={v} /></Section>
        <Section title="Size and fit"><SizeAndFit d={d} set={setD} vocab={v} /></Section>
        <Section title="Your mannequin"><MannequinSection /></Section>
        <Section title="Budget per piece"><Budgets d={d} set={setD} /></Section>
        <Section title="Fabrics"><Materials d={d} set={setD} vocab={v} /></Section>
        <Section title="Colours and occasions"><ColoursAndOccasions d={d} set={setD} vocab={v} /></Section>
      </div>
      {save.error && <div className="section"><ErrorBox error={save.error} /></div>}
      <div className="section row">
        <button className="btn btn-primary" disabled={save.isPending || !d.name.trim()}>
          {save.isPending ? <span className="spinner" /> : <Icon name="check" />} Save
        </button>
      </div>
    </form>
  );
}

import { createFileRoute } from "@tanstack/react-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { PageHead } from "@/components/wiw/bits";
import { AboutFields, BudgetFields, ColourFields, FabricFields, MannequinFields, SizeFields, prefsPayload, type PrefDraft } from "@/components/wiw/PrefFields";
import { api, errorText } from "@/lib/api";
import { getVocab } from "@/lib/data";
import { getState, refreshMe, refreshRail, setMannequin, updateProfile } from "@/lib/store";

export const Route = createFileRoute("/preferences")({
  head: () => ({ meta: [{ title: "Preferences · Atelier" }] }),
  component: Prefs,
});

function Card({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="rounded-[20px] border border-border bg-card p-5 sm:p-6">
      <h2 className="display mb-5 text-2xl">{title}</h2>
      {children}
    </section>
  );
}

function Prefs() {
  const qc = useQueryClient();
  const { data: vocab } = useQuery({ queryKey: ["vocab"], queryFn: getVocab });
  const [saving, setSaving] = useState(false);
  const [d, setD] = useState<PrefDraft>(() => {
    const { me, mannequin } = getState();
    const p = me?.preferences;
    return {
      name: me?.name ?? "",
      city: me?.city ?? "Bengaluru",
      gender_fit: p?.gender_fit ?? "women",
      sizes: p?.sizes ?? {},
      fit: p?.fit ?? "regular",
      body: mannequin.body,
      tone: mannequin.tone,
      budgets: p?.budgets ?? {},
      preferred_materials: p?.preferred_materials ?? [],
      avoid_materials: p?.avoid_materials ?? [],
      avoid_colors: p?.avoid_colors ?? [],
      occasions: p?.occasions ?? [],
      bring_purchases: true,
    };
  });
  const set = (p: Partial<PrefDraft>) => setD((x) => ({ ...x, ...p }));

  const save = async () => {
    if (!d.name.trim()) return toast.error("Your name can't be empty");
    setSaving(true);
    try {
      await updateProfile({ name: d.name.trim(), city: d.city });
      await setMannequin(d.body, d.tone);
      await api.put("/preferences", prefsPayload(d));
      await Promise.all([refreshMe(), refreshRail()]);
      ["shop", "product", "piece-matches", "tray"].forEach((k) => void qc.invalidateQueries({ queryKey: [k] }));
      toast.success("Saved. Your matches are updated.");
    } catch (e) {
      toast.error(errorText(e));
    } finally {
      setSaving(false);
    }
  };

  if (!vocab) return <div className="shimmer h-96 rounded-[20px]" />;
  const saveButton = (
    <Button variant="hero" onClick={() => void save()} disabled={saving}>
      {saving && <Loader2 className="animate-spin" />} Save changes
    </Button>
  );
  return (
    <>
      <PageHead
        eyebrow="Your profile"
        title="Preferences"
        intro="These are soft preferences. Matches that fit them show under For you; great matches that don't are still shown under Also view, with the reason."
        actions={saveButton}
      />
      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="About you"><AboutFields d={d} set={set} vocab={vocab} /></Card>
        <Card title="Size and fit"><SizeFields d={d} set={set} vocab={vocab} /></Card>
        <div className="lg:col-span-2"><Card title="Your mannequin"><MannequinFields d={d} set={set} /></Card></div>
        <Card title="Budget per piece"><BudgetFields d={d} set={set} /></Card>
        <Card title="Fabrics"><FabricFields d={d} set={set} vocab={vocab} /></Card>
        <div className="lg:col-span-2"><Card title="Colours and occasions"><ColourFields d={d} set={set} vocab={vocab} /></Card></div>
      </div>
      <div className="mt-8 flex justify-end">{saveButton}</div>
    </>
  );
}

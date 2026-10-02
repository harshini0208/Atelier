import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { ArrowLeft, ArrowRight, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { api, errorText, setCurrentUserId } from "@/lib/api";
import { getVocab } from "@/lib/data";
import { loadSession, resetSession } from "@/lib/store";
import { AboutFields, BudgetFields, ColourFields, FabricFields, MannequinFields, SizeFields, prefsPayload, type PrefDraft } from "@/components/wiw/PrefFields";

export const Route = createFileRoute("/welcome")({
  head: () => ({ meta: [{ title: "Welcome · Atelier" }] }),
  component: Welcome,
});

const STEPS = [
  { title: "Welcome to Atelier", intro: "Everything you buy, bag and love at Urban Thread on one rail, ready to hang in folders and style." },
  { title: "Your sizes and fit", intro: "So we only show you what fits, and tell you when your size is gone." },
  { title: "Your mannequin", intro: "Pick the body type and finish closest to yours. We dress your looks on it so you can see how they fit." },
  { title: "Budget per piece", intro: "Matches that fit show under For you; great ones that don't are still there under Also view." },
  { title: "Fabrics", intro: "What feels good on you, and what you'd rather not wear." },
  { title: "Colours and occasions", intro: "Last one. What you dress for, and any colours to skip." },
];

function Welcome() {
  const navigate = useNavigate();
  const { data: vocab } = useQuery({ queryKey: ["vocab"], queryFn: getVocab });
  const [step, setStep] = useState(0);
  const [busy, setBusy] = useState(false);
  const [d, setD] = useState<PrefDraft>({
    name: "",
    city: "Bengaluru",
    gender_fit: "women",
    sizes: { tops: "M", bottoms: "28", footwear: "6" },
    fit: "regular",
    body: "slim",
    tone: "tan",
    budgets: { tops: [500, 2500], bottoms: [800, 3000], one_piece: [1500, 5000], outerwear: [2000, 5000] },
    preferred_materials: [],
    avoid_materials: [],
    avoid_colors: [],
    occasions: [],
    bring_purchases: true,
  });
  const set = (p: Partial<PrefDraft>) => setD((x) => ({ ...x, ...p }));
  const cur = STEPS[step]!;
  const last = step === STEPS.length - 1;

  const finish = async () => {
    setBusy(true);
    try {
      const r = await api.post<{ id: string }>("/profile", { name: d.name.trim(), ...prefsPayload(d) });
      setCurrentUserId(r.id);
      await api.put("/mannequin", { body_type: d.body, skin_tone: d.tone }).catch(() => undefined);
      if (d.bring_purchases) await api.post("/membership/link").catch(() => undefined);   // optional; never blocks sign-up
      resetSession();
      await loadSession(true);
      await navigate({ to: "/" });
    } catch (e) {
      toast.error(errorText(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen">
      <header className="mx-auto flex h-16 max-w-3xl items-center gap-2 px-5">
        <span className="brand-script text-[42px] text-foreground">Atelier</span>
        <span className="eyebrow ml-auto">Urban Thread</span>
      </header>
      <main className="mx-auto max-w-3xl px-5 pb-16 pt-6 sm:pt-12">
        <div className="mb-8 grid grid-cols-6 gap-1.5" aria-hidden>
          {STEPS.map((_, i) => (
            <div key={i} className={i <= step ? "h-0.5 rounded-full bg-foreground" : "h-0.5 rounded-full bg-border"} />
          ))}
        </div>
        <p className="eyebrow mb-3">Step {step + 1} of 6</p>
        <h1 className="display text-4xl sm:text-6xl">
          {step === 0 ? <>Welcome to <span className="brand-script inline-block text-[1.3em]">Atelier</span></> : cur.title}
        </h1>
        <p className="mt-4 max-w-lg text-sm leading-relaxed text-muted-foreground sm:text-base">{cur.intro}</p>

        <section data-theme="sky-studio" className="mt-10 onboarding-card rounded-[20px] border border-border p-5 sm:p-8">
          {!vocab ? (
            <div className="shimmer h-48 rounded-[14px]" />
          ) : (
            <>
              {step === 0 && <AboutFields d={d} set={set} vocab={vocab} />}
              {step === 1 && <SizeFields d={d} set={set} vocab={vocab} />}
              {step === 2 && <MannequinFields d={d} set={set} />}
              {step === 3 && <BudgetFields d={d} set={set} />}
              {step === 4 && <FabricFields d={d} set={set} vocab={vocab} />}
              {step === 5 && (
                <>
                  <ColourFields d={d} set={set} vocab={vocab} />
                  <label className="mt-6 flex min-h-12 cursor-pointer items-center gap-3 rounded-[14px] bg-muted px-4 py-3">
                    <Checkbox checked={d.bring_purchases} onCheckedChange={(v) => set({ bring_purchases: !!v })} />
                    <span className="text-sm">
                      Bring in my Urban Thread purchases
                      <span className="block text-xs text-muted-foreground">
                        Link your membership so pieces you bought online and in store show on your rail. <i>Demo: a sample purchase history is added.</i>
                      </span>
                    </span>
                  </label>
                </>
              )}
            </>
          )}
          <div className="mt-8 flex items-center gap-2 border-t border-border pt-6">
            {step > 0 && (
              <Button variant="ghost" onClick={() => setStep(step - 1)}>
                <ArrowLeft /> Back
              </Button>
            )}
            <div className="ml-auto flex gap-2">
              {step > 0 && !last && (
                <Button variant="ghost" onClick={() => setStep(step + 1)}>Skip</Button>
              )}
              <Button
                variant="hero"
                disabled={(step === 0 && !d.name.trim()) || busy}
                onClick={() => (last ? void finish() : setStep(step + 1))}
              >
                {busy && <Loader2 className="animate-spin" />}
                {last ? "Open my wardrobe" : "Next"} <ArrowRight />
              </Button>
            </div>
          </div>
        </section>
        <p className="mt-4 text-center text-xs text-muted-foreground">You can change any of this later in Preferences.</p>
      </main>
    </div>
  );
}

import { createFileRoute } from "@tanstack/react-router";
import { useMemo } from "react";
import { PageHead, SectionHead } from "@/components/wiw/bits";
import { useStore } from "@/lib/store";

export const Route = createFileRoute("/taste")({
  head: () => ({ meta: [{ title: "My taste · Atelier" }] }),
  component: Taste,
});

function tally(values: string[]) {
  const m = new Map<string, number>();
  values.forEach((v) => m.set(v, (m.get(v) ?? 0) + 1));
  return [...m.entries()].sort((a, b) => b[1] - a[1]).slice(0, 6);
}

function Bars({ title, rows }: { title: string; rows: [string, number][] }) {
  const max = Math.max(1, ...rows.map((r) => r[1]));
  return (
    <section>
      <SectionHead title={title} />
      <ul className="space-y-3">
        {rows.map(([k, n]) => (
          <li key={k} className="grid grid-cols-[100px_1fr_24px] items-center gap-3 text-sm">
            <span className="capitalize">{k.replace(/_/g, " ")}</span>
            <span className="h-1.5 overflow-hidden rounded-full bg-muted">
              <span className="block h-full rounded-full bg-primary" style={{ width: `${(n / max) * 100}%` }} />
            </span>
            <span className="text-right text-xs text-muted-foreground">{n}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function Taste() {
  const rail = useStore((s) => s.rail);
  const products = useMemo(() => rail?.items.map((i) => i.product) ?? [], [rail]);
  const colors = tally(products.map((p) => p.primary_color));
  const top = colors[0]?.[0];
  if (!products.length)
    return (
      <>
        <PageHead eyebrow="Read from your rail" title="My taste" />
        <p className="text-sm text-muted-foreground">Your taste shows up here once your rail has a few pieces: heart some in the shop or link your membership.</p>
      </>
    );
  return (
    <>
      <PageHead
        eyebrow="Read from your rail"
        title="My taste"
        intro={top ? `You keep reaching for ${top.replace(/_/g, " ")}, in ${tally(products.map((p) => p.fabric))[0]?.[0]}. Here's what your wardrobe says about you.` : undefined}
      />
      <div className="mb-12 grid grid-cols-3 gap-2 sm:grid-cols-6">
        {products.slice(0, 6).map((p) => (
          <img key={p.id} src={p.image_url} alt={p.name} className="aspect-[3/4] w-full rounded-[14px] object-cover" />
        ))}
      </div>
      <div className="grid gap-10 md:grid-cols-2">
        <Bars title="Colours" rows={colors} />
        <Bars title="Fabrics" rows={tally(products.map((p) => p.fabric))} />
        <Bars title="Styles" rows={tally(products.flatMap((p) => p.style_tags))} />
        <Bars title="Occasions" rows={tally(products.flatMap((p) => p.occasion_tags))} />
      </div>
    </>
  );
}

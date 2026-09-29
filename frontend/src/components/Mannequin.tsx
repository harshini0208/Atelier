import { useDroppable } from "@dnd-kit/core";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api";
import type { Product } from "../types";

export type Avatar = {
  presentation: "women" | "men"; body_type: string; height_band: string; skin_tone: number; hair_style: string; hair_color: string;
};
type Transform = { slot: string; z: number; x: number; y: number; sx: number; sy: number };
export type MannequinGeo = {
  width: number; height: number; body: string; hair_front: string;
  transforms: Record<string, Transform>;
  drop_zones: Record<string, { x: number; y: number; w: number; h: number; label: string }>;
};

export function useMannequin(a: Avatar | undefined) {
  const qs = a ? new URLSearchParams({ ...a, skin_tone: String(a.skin_tone) } as Record<string, string>).toString() : "";
  return useQuery({ queryKey: ["mannequin", qs], queryFn: () => api.get<MannequinGeo>(`/mannequin?${qs}`), enabled: !!a,
    staleTime: Infinity, placeholderData: (prev) => prev });
}

function Zone({ id, z, width, height, active }: { id: string; z: { x: number; y: number; w: number; h: number; label: string };
  width: number; height: number; active: boolean }) {
  const { setNodeRef, isOver } = useDroppable({ id: `zone-${id}` });
  return (
    <div ref={setNodeRef} aria-label={`${z.label} area`} style={{
      position: "absolute", left: `${(z.x / width) * 100}%`, top: `${(z.y / height) * 100}%`,
      width: `${(z.w / width) * 100}%`, height: `${(z.h / height) * 100}%`, borderRadius: 10,
      border: active ? `1.5px dashed ${isOver ? "var(--sage)" : "rgba(79,97,69,.45)"}` : "none",
      background: isOver ? "rgba(79,97,69,.14)" : "transparent", transition: "background .12s",
      display: "grid", placeItems: "center", pointerEvents: active ? "auto" : "none" }}>
      {active && <span style={{ fontSize: 10, fontWeight: 700, color: "var(--sage)", background: "rgba(255,255,255,.8)", padding: "1px 5px", borderRadius: 4 }}>{z.label}</span>}
    </div>
  );
}

export default function MannequinStage({ geo, placed, dragging, onRemove, compact = false }: {
  geo: MannequinGeo | undefined; placed: Product[]; dragging: boolean; onRemove?: (p: Product) => void; compact?: boolean;
}) {
  const { setNodeRef, isOver } = useDroppable({ id: "stage" });
  if (!geo) return <div className="skeleton" style={{ aspectRatio: "9/16", maxWidth: 380, margin: "0 auto" }} />;
  const sorted = [...placed].sort((a, b) => (geo.transforms[a.subcategory]?.z ?? 0) - (geo.transforms[b.subcategory]?.z ?? 0));
  const W = geo.width, H = geo.height;
  // crop the empty margins around the figure
  const vb = `60 60 ${W - 120} ${H - 80}`;
  return (
    <div ref={setNodeRef} style={{ position: "relative", maxWidth: compact ? 220 : 400, margin: "0 auto", borderRadius: 18,
      background: "radial-gradient(ellipse at 50% 30%, #fbf8f3 0%, #efe7dc 70%)", outline: isOver ? "2px solid var(--sage)" : "none" }}>
      <svg viewBox={vb} style={{ width: "100%", display: "block" }} role="img"
        aria-label={placed.length ? `Mannequin wearing ${placed.map((p) => p.name).join(", ")}` : "Empty mannequin"}>
        <ellipse cx={W / 2} cy={H - 70} rx={120} ry={14} fill="#000" opacity={0.06} />
        <g dangerouslySetInnerHTML={{ __html: geo.body }} />
        {sorted.map((p) => {
          const t = geo.transforms[p.subcategory];
          if (!t) return null;
          return (
            <g key={p.id} transform={`translate(${t.x} ${t.y}) scale(${t.sx} ${t.sy})`} style={{ cursor: onRemove ? "pointer" : "default" }}
              onClick={() => onRemove?.(p)}>
              <title>{p.name}{onRemove ? " (click to take off)" : ""}</title>
              <image href={p.image_url} width={200} height={200} preserveAspectRatio="none" />
            </g>
          );
        })}
        <g dangerouslySetInnerHTML={{ __html: geo.hair_front }} style={{ pointerEvents: "none" }} />
      </svg>
      {!compact && (
        <div style={{ position: "absolute", inset: 0, pointerEvents: "none" }}>
          <div style={{ position: "absolute", left: `${-60 / (W - 120) * 100}%`, top: `${-60 / (H - 80) * 100}%`,
            width: `${W / (W - 120) * 100}%`, height: `${H / (H - 80) * 100}%` }}>
            {Object.entries(geo.drop_zones).map(([id, z]) => <Zone key={id} id={id} z={z} width={W} height={H} active={dragging} />)}
          </div>
        </div>
      )}
    </div>
  );
}

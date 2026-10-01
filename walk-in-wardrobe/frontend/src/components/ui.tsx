import { createContext, ReactNode, useCallback, useContext, useEffect, useRef, useState } from "react";
import { inr } from "../api";
import type { Coverage, MatchItem, Product } from "../types";

// ------------------------------------------------------------------ icons
const paths: Record<string, string> = {
  home: "M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6h-6v6H4a1 1 0 0 1-1-1z",
  plus: "M12 5v14M5 12h14",
  x: "M6 6l12 12M18 6 6 18",
  upload: "M12 16V4m0 0-5 5m5-5 5 5M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3",
  sliders: "M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12M20 18h0M14 4v4M8 10v4M16 16v4",
  bag: "M5 8h14l-1 12H6zM9 8V6a3 3 0 0 1 6 0v2",
  bell: "M6 16V11a6 6 0 0 1 12 0v5l2 2H4zM10 20a2 2 0 0 0 4 0",
  chat: "M4 5h16v11H9l-5 4z",
  sparkle: "M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8zM19 16l.8 2.2L22 19l-2.2.8L19 22l-.8-2.2L16 19l2.2-.8z",
  hanger: "M12 6a2 2 0 1 1 2 2c-1 .4-2 1-2 2v1l9 6.5c.8.6.4 1.5-.5 1.5h-17c-.9 0-1.3-.9-.5-1.5L12 11",
  user: "M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM4 21a8 8 0 0 1 16 0",
  chart: "M4 20V10M10 20V4M16 20v-7M22 20H2",
  bolt: "M13 2 4 14h7l-1 8 9-12h-7z",
  check: "M5 12l5 5L20 7",
  arrow: "M5 12h14M13 6l6 6-6 6",
  back: "M19 12H5M11 6l-6 6 6 6",
  tag: "M3 12V4h8l10 10-8 8zM7.5 7.5h0",
  trash: "M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13",
  undo: "M9 14 4 9l5-5M4 9h11a5 5 0 0 1 0 10h-3",
  heart: "M12 20C12 20 3 14.5 3 9c0-3 2.2-5 4.6-5 2 0 3.6 1.2 4.4 3 .8-1.8 2.4-3 4.4-3C18.8 4 21 6 21 9c0 5.5-9 11-9 11z",
  store: "M4 9l1.5-5h13L20 9M4 9h16v11H4zM4 9c0 1.7 1.3 3 3 3s3-1.3 3-3c0 1.7 1.3 3 2 3s2-1.3 2-3c0 1.7 1.3 3 3 3s3-1.3 3-3M10 20v-5h4v5",
  folder: "M3 6a1 1 0 0 1 1-1h5l2 2h9a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1z",
};

export function Icon({ name, size = 20, title }: { name: keyof typeof paths | string; size?: number; title?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.7}
      strokeLinecap="round" strokeLinejoin="round" aria-hidden={title ? undefined : true} role={title ? "img" : undefined}>
      {title && <title>{title}</title>}
      <path d={paths[name] ?? ""} />
    </svg>
  );
}

// ------------------------------------------------------------------ toast
const ToastCtx = createContext<(msg: string) => void>(() => {});
export const useToast = () => useContext(ToastCtx);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [msg, setMsg] = useState<string | null>(null);
  const timer = useRef<number>();
  const show = useCallback((m: string) => {
    setMsg(m);
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => setMsg(null), 3200);
  }, []);
  return (
    <ToastCtx.Provider value={show}>
      {children}
      {msg && <div className="toast" role="status" aria-live="polite">{msg}</div>}
    </ToastCtx.Provider>
  );
}

// ------------------------------------------------------------------ overlays
function useEscape(onClose: () => void) {
  useEffect(() => {
    const h = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", h);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", h);
      document.body.style.overflow = prev;
    };
  }, [onClose]);
}

export function Sheet({ title, onClose, children, head }: { title: string; onClose: () => void; children: ReactNode; head?: ReactNode }) {
  useEscape(onClose);
  return (
    <>
      <div className="overlay" onClick={onClose} />
      <section className="sheet" role="dialog" aria-modal="true" aria-label={title}>
        <div className="sheet-grip" />
        <div className="sheet-head">
          <div style={{ flex: 1, minWidth: 0 }}>{head ?? <h2>{title}</h2>}</div>
          <button className="icon-btn" onClick={onClose} aria-label="Close"><Icon name="x" /></button>
        </div>
        <div className="sheet-body">{children}</div>
      </section>
    </>
  );
}

export function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  useEscape(onClose);
  return (
    <>
      <div className="overlay modal-overlay" onClick={onClose} />
      <section className="modal" role="dialog" aria-modal="true" aria-label={title}>
        <div className="row-between" style={{ padding: "14px 16px 0" }}>
          <h2>{title}</h2>
          <button className="icon-btn" onClick={onClose} aria-label="Close"><Icon name="x" /></button>
        </div>
        <div style={{ padding: 16 }}>{children}</div>
      </section>
    </>
  );
}

// ------------------------------------------------------------------ states
export function Loading({ label = "Loading" }: { label?: string }) {
  return (
    <div className="row muted" role="status" style={{ padding: 16 }}>
      <span className="spinner" /> {label}…
    </div>
  );
}

export function ErrorBox({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const msg = error instanceof Error ? error.message : "Something went wrong.";
  return (
    <div className="alert alert-rose row-between" role="alert">
      <span>{msg}</span>
      {onRetry && <button className="btn btn-sm" onClick={onRetry}>Try again</button>}
    </div>
  );
}

export function SkeletonGrid({ n = 6 }: { n?: number }) {
  return (
    <div className="product-grid" aria-hidden>
      {Array.from({ length: n }, (_, i) => <div key={i} className="skeleton" style={{ aspectRatio: "3/4" }} />)}
    </div>
  );
}

// ------------------------------------------------------------------ commerce bits
export function Price({ price, mrp }: { price: number; mrp?: number }) {
  return (
    <span className="price">
      {inr(price)}
      {mrp && mrp > price ? <span className="mrp">{inr(mrp)}</span> : null}
    </span>
  );
}

export function ProductCard({ item, product, onOpen, badge }: {
  item?: MatchItem; product?: Product; onOpen: (p: Product) => void; badge?: ReactNode;
}) {
  const p = item?.product ?? product!;
  return (
    <button className="product-card" onClick={() => onOpen(p)} aria-label={`${p.name}, ${inr(p.price_inr)}`}>
      <div className="product-img"><img src={p.image_url} alt={`${p.name} flat-lay`} loading="lazy" /></div>
      <div className="product-body">
        <span className="name">{p.name}</span>
        <Price price={p.price_inr} mrp={p.mrp_inr} />
        {item && (
          <>
            <div className="score-bar" title={`Style match ${Math.round(item.score)}/100`}>
              <span style={{ width: `${Math.min(100, item.score)}%` }} />
            </div>
            <span className="sr-only">Style match {Math.round(item.score)} out of 100</span>
          </>
        )}
        {badge}
        {item && item.reasons.length > 0 && (
          <div className="chips">{item.reasons.map((r) => <span key={r.label} className="chip chip-amber">{r.label}</span>)}</div>
        )}
        {item && item.reasons.length === 0 && item.why.length > 0 && (
          <div className="chips">{item.why.slice(0, 2).map((w) => <span key={w} className="chip chip-sage">{w}</span>)}</div>
        )}
      </div>
    </button>
  );
}

export function CoverageLine({ coverage }: { coverage: Coverage }) {
  const dots = coverage.pieces?.length ? coverage.pieces : Array.from({ length: coverage.total }, (_, i) => ({
    hanger_id: i, name: "", subcategory: "", covered: i < coverage.covered, covered_in_prefs: i < coverage.covered_in_prefs }));
  return (
    <div className="coverage" role="status">
      <div className="coverage-dots" aria-hidden>
        {dots.map((d) => <span key={d.hanger_id} className={d.covered_in_prefs ? "pref" : d.covered ? "cov" : ""} title={d.name} />)}
      </div>
      <div>
        <div style={{ fontWeight: 600, fontSize: 14 }}>{coverage.line}</div>
        {coverage.pieces?.some((p) => !p.covered) && (
          <div className="small muted">
            Not in store yet: {coverage.pieces.filter((p) => !p.covered).map((p) => p.name.toLowerCase()).join(", ")}
          </div>
        )}
      </div>
    </div>
  );
}

export function ColorDot({ hex, label }: { hex: string; label: string }) {
  return <span className="swatch" style={{ background: hex }} title={label} aria-label={label} />;
}

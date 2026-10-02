import { cn } from "@/lib/utils";
import { CheckCircle2, AlertTriangle, XCircle, ShoppingBag, Store, Heart, Package } from "lucide-react";
import type { ReactNode } from "react";
import type { RailSource } from "@/lib/types";

export function Chip({
  active,
  children,
  onClick,
  className,
}: {
  active?: boolean;
  children: ReactNode;
  onClick?: () => void;
  className?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        "inline-flex min-h-9 shrink-0 items-center gap-1.5 rounded-full border px-3.5 text-xs font-medium transition-colors",
        active
          ? "border-primary bg-primary text-primary-foreground"
          : "border-border bg-card text-foreground hover:bg-muted",
        className,
      )}
    >
      {children}
    </button>
  );
}

export function Brand({ className }: { className?: string }) {
  return <span className={cn("brand-script inline-block leading-none", className)}>Atelier</span>;
}

export function SectionHead({ title, meta, action, scriptTitle = false }: { title: string; meta?: ReactNode; action?: ReactNode; scriptTitle?: boolean }) {
  return (
    <div className="mb-4 flex items-end justify-between gap-4 border-b border-border pb-3">
      <h2 className={scriptTitle ? "brand-script text-[38px] sm:text-[44px]" : "display text-2xl sm:text-3xl"}>{title}</h2>
      <div className="flex shrink-0 items-center gap-3 text-xs text-muted-foreground">
        {meta}
        {action}
      </div>
    </div>
  );
}

export function PageHead({ eyebrow, title, intro, actions, scriptTitle = false }: { eyebrow?: string; title: string; intro?: ReactNode; actions?: ReactNode; scriptTitle?: boolean }) {
  return (
    <header className="mb-8 flex flex-col gap-5 sm:mb-10 lg:flex-row lg:items-end lg:justify-between">
      <div className="min-w-0 max-w-xl">
        {eyebrow && <p className="eyebrow mb-3">{eyebrow}</p>}
        <h1 className={scriptTitle ? "brand-script text-[56px] sm:text-[64px]" : "display text-4xl sm:text-5xl"}>{title}</h1>
        {intro && <p className="mt-3 text-sm leading-relaxed text-muted-foreground sm:text-base">{intro}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </header>
  );
}

const sourceIcon = { online: Package, in_store: Store, cart: ShoppingBag, wishlist: Heart } as const;
export function SourceTag({ source }: { source: RailSource }) {
  const Icon = sourceIcon[source.kind];
  return (
    <span className="glass inline-flex items-center gap-1 rounded-full px-2 py-1 text-[10px] font-semibold text-accent-foreground">
      <Icon className="size-3" aria-hidden />
      {source.label}
    </span>
  );
}

export function Status({ kind, children }: { kind: "ok" | "warn" | "danger"; children: ReactNode }) {
  const Icon = kind === "ok" ? CheckCircle2 : kind === "warn" ? AlertTriangle : XCircle;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 text-xs font-medium",
        kind === "ok" && "text-ok",
        kind === "warn" && "text-warn",
        kind === "danger" && "text-danger",
      )}
    >
      <Icon className="size-3.5" aria-hidden />
      {children}
    </span>
  );
}

export function ProductImage({ src, alt, className }: { src: string; alt: string; className?: string }) {
  return (
    <div className={cn("overflow-hidden rounded-[18px] bg-muted", className)}>
      <img src={src} alt={alt} loading="lazy" className="h-full w-full object-cover" />
    </div>
  );
}

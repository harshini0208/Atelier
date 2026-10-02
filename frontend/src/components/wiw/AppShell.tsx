import type { ReactNode } from "react";
import { Link } from "@tanstack/react-router";
import { Bell, ShoppingBag, Shirt, Tag, Sparkles, SlidersHorizontal, Check } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { THEMES, applyTheme, useStore, type ThemeId } from "@/lib/store";
import { openStylist, useUI } from "@/lib/ui";
import { api, setCurrentUserId } from "@/lib/api";
import { StylistPanel } from "./Stylist";
import { HangSheet, ProductSheet } from "./Sheets";
import { useEffect, useState } from "react";

const NAV = [
  { to: "/", label: "Wardrobe", icon: Shirt },
  { to: "/shop", label: "Shop", icon: Tag },
  { to: "/taste", label: "My taste", icon: Sparkles },
  { to: "/preferences", label: "Preferences", icon: SlidersHorizontal },
] as const;

/* One swatch per theme, painted by the theme itself so no colour is hard-coded. */
function Swatch({ id }: { id: ThemeId }) {
  return (
    <span data-theme={id} className="flex size-8 overflow-hidden rounded-full border border-border">
      <span className="h-full w-1/2 bg-background" />
      <span className="h-full w-1/2 bg-hero" />
    </span>
  );
}

function ProfileMenu() {
  const me = useStore((s) => s.me);
  const [theme, setTheme] = useState<string>("sky-studio");
  useEffect(() => {
    setTheme(document.documentElement.dataset["theme"] ?? "sky-studio");
  }, []);
  const initial = (me?.name ?? "?").charAt(0).toUpperCase();
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          aria-label="Profile menu"
          className="flex h-11 items-center gap-2 rounded-full pl-1 pr-1 hover:bg-muted sm:pr-3"
        >
          <span className="grid size-8 place-items-center rounded-full bg-accent text-xs font-semibold text-accent-foreground">
            {initial}
          </span>
          <span className="hidden text-xs font-medium sm:inline">{me?.name}</span>
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-64 rounded-[16px] border-border bg-card p-2">
        <DropdownMenuLabel className="text-xs text-muted-foreground">Palette</DropdownMenuLabel>
        <div className="grid grid-cols-5 gap-1 px-1 pb-2" role="radiogroup" aria-label="Theme">
          {THEMES.map((t) => (
            <button
              key={t.id}
              role="radio"
              aria-checked={theme === t.id}
              aria-label={t.label}
              title={t.label}
              onClick={() => {
                applyTheme(t.id);
                setTheme(t.id);
              }}
              className="relative grid h-11 place-items-center rounded-full"
            >
              <Swatch id={t.id} />
              {theme === t.id && (
                <Check className="absolute -right-0.5 -top-0.5 size-4 rounded-full bg-primary p-0.5 text-primary-foreground" />
              )}
            </button>
          ))}
        </div>
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild><Link to="/cart">Cart & orders</Link></DropdownMenuItem>
        <DropdownMenuItem asChild><Link to="/notifications">Notifications</Link></DropdownMenuItem>
        <DropdownMenuItem asChild><Link to="/preferences">Preferences</Link></DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem
          onClick={() => {
            if (!confirm("Start over with a new profile on this device? Your current wardrobe stays saved but you'll be signed out of it.")) return;
            setCurrentUserId(null);
            window.location.assign("/welcome");
          }}
        >
          Start over as someone new
        </DropdownMenuItem>
        <DropdownMenuItem
          className="text-danger"
          onClick={async () => {
            if (!confirm("Delete your profile, folders, hangers, cart and orders? This can't be undone.")) return;
            await api.del("/me");
            setCurrentUserId(null);
            window.location.assign("/welcome");
          }}
        >
          Delete my profile & data
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function IconLink({ to, label, count, children }: { to: "/cart" | "/notifications"; label: string; count: number; children: ReactNode }) {
  return (
    <Link to={to} aria-label={count ? `${label}, ${count}` : label} className="relative grid size-11 place-items-center rounded-full hover:bg-muted">
      {children}
      {count > 0 && (
        <span className="absolute right-1.5 top-1.5 grid min-w-4 place-items-center rounded-full bg-primary px-1 text-[9px] font-bold text-primary-foreground">
          {count}
        </span>
      )}
    </Link>
  );
}

/** True on screens wide enough for the stylist column (so the chat is only ever mounted once). */
function useDesktop() {
  const q = "(min-width: 1024px)";
  const [on, setOn] = useState(() => window.matchMedia(q).matches);
  useEffect(() => {
    const m = window.matchMedia(q);
    const h = () => setOn(m.matches);
    m.addEventListener("change", h);
    return () => m.removeEventListener("change", h);
  }, []);
  return on;
}

export function AppShell({ children }: { children: ReactNode }) {
  const desktop = useDesktop();
  const cartCount = useStore((s) => s.cart.reduce((a, c) => a + c.qty, 0));
  const unread = useStore((s) => s.notifications.filter((n) => !n.read).length);
  const stylistOpen = useUI((u) => u.stylistOpen);

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[minmax(0,1fr)_360px]">
      <div className="min-w-0 pb-28 lg:pb-0">
        <header data-theme="sky-studio" className="app-header sticky top-0 z-30 border-b border-border">
          <div className="mx-auto flex h-16 max-w-6xl items-center gap-6 px-5 sm:px-8">
            <Link to="/" className="flex min-w-0 items-center gap-2" aria-label="Atelier home">
              <span className="brand-script block whitespace-nowrap text-[38px] text-foreground sm:text-[42px]">Atelier</span>
            </Link>
            <nav className="hidden items-center gap-1 md:flex" aria-label="Main">
              {NAV.map((n) => (
                <Link
                  key={n.to}
                  to={n.to}
                  activeOptions={{ exact: n.to === "/" }}
                  className="rounded-full px-3 py-2 text-xs font-medium text-muted-foreground hover:text-foreground"
                  activeProps={{ className: "bg-muted !text-foreground" }}
                >
                  {n.label}
                </Link>
              ))}
            </nav>
            <div className="ml-auto flex items-center gap-1">
              <IconLink to="/notifications" label="Notifications" count={unread}>
                <Bell className="size-[18px]" />
              </IconLink>
              <IconLink to="/cart" label="Cart" count={cartCount}>
                <ShoppingBag className="size-[18px]" />
              </IconLink>
              <ProfileMenu />
            </div>
          </div>
        </header>
        <main className="mx-auto max-w-6xl px-5 py-8 sm:px-8 sm:py-12">{children}</main>
      </div>

      {desktop && (
        <aside className="sticky top-0 h-screen border-l border-border" aria-label="Stylist">
          <StylistPanel />
        </aside>
      )}

      {/* mobile */}
      <Button
        variant="hero"
        className="fixed bottom-24 right-5 z-30 shadow-lg lg:hidden"
        onClick={() => openStylist(true)}
      >
        <Sparkles /> Stylist
      </Button>
      <Sheet open={stylistOpen && !desktop} onOpenChange={openStylist}>
        <SheetContent side="bottom" className="h-[85vh] overflow-hidden rounded-t-[24px] border-border bg-background p-0">
          <SheetTitle className="sr-only">Stylist chat</SheetTitle>
          <StylistPanel />
        </SheetContent>
      </Sheet>
      <nav
        aria-label="Main"
        className="fixed inset-x-4 bottom-4 z-30 flex justify-around rounded-full border border-border bg-card/95 pb-[max(env(safe-area-inset-bottom),0.25rem)] pt-1 shadow-lg backdrop-blur md:hidden"
      >
        {NAV.map((n) => (
          <Link
            key={n.to}
            to={n.to}
            activeOptions={{ exact: n.to === "/" }}
            className="flex min-h-12 min-w-16 flex-col items-center justify-center gap-0.5 rounded-full text-[11px] text-muted-foreground"
            activeProps={{ className: "!text-foreground font-semibold" }}
          >
            <n.icon className="size-5" aria-hidden />
            {n.label}
          </Link>
        ))}
      </nav>

      <ProductSheet />
      <HangSheet />
    </div>
  );
}

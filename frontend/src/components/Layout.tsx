import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ReactNode, useEffect, useRef, useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { api, currentUserId, setCurrentUserId } from "../api";
import type { Me, Persona, Vocab } from "../types";
import { Icon } from "./ui";

export function useMe() {
  return useQuery({ queryKey: ["me"], queryFn: () => api.get<Me>("/me") });
}

export function useVocab() {
  return useQuery({ queryKey: ["vocab"], queryFn: () => api.get<Vocab>("/vocab"), staleTime: Infinity });
}

export type NavItem = { to: string; label: string; icon: string; mobile?: boolean };

export const NAV: NavItem[] = [
  { to: "/", label: "Wardrobes", icon: "hanger", mobile: true },
  { to: "/preferences", label: "Preferences", icon: "sliders", mobile: true },
];

export function registerNav(item: NavItem) {
  if (!NAV.some((n) => n.to === item.to)) NAV.push(item);
}

function PersonaMenu() {
  const qc = useQueryClient();
  const nav = useNavigate();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const { data: me } = useMe();
  const { data: personas } = useQuery({ queryKey: ["personas"], queryFn: () => api.get<Persona[]>("/personas") });

  useEffect(() => {
    const h = (e: MouseEvent) => ref.current && !ref.current.contains(e.target as Node) && setOpen(false);
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, []);

  const switchTo = async (id: string | null) => {
    if (id === null) id = (await api.post<{ id: string }>("/guest")).id;
    setCurrentUserId(id);
    setOpen(false);
    qc.clear();
    nav("/");
  };

  return (
    <div ref={ref} style={{ position: "relative" }}>
      <button className="btn btn-sm btn-ghost" onClick={() => setOpen((o) => !o)} aria-haspopup="menu" aria-expanded={open}>
        <span aria-hidden style={{ width: 26, height: 26, borderRadius: 99, background: "#e3d9cb", display: "grid", placeItems: "center", fontFamily: "var(--serif)" }}>
          {me?.name?.[0] ?? "·"}
        </span>
        <span className="persona-name">{me?.name ?? "…"}</span>
      </button>
      {open && (
        <div role="menu" className="card" style={{ position: "absolute", right: 0, top: 46, width: 260, padding: 6, zIndex: 50 }}>
          <div className="eyebrow" style={{ padding: "6px 10px" }}>Demo shoppers</div>
          {personas?.map((p) => (
            <button key={p.id} role="menuitem" className="btn btn-ghost btn-block" style={{ justifyContent: "flex-start", height: "auto", padding: "8px 10px", fontWeight: 500 }}
              onClick={() => switchTo(p.id)}>
              <span style={{ textAlign: "left" }}>
                <b>{p.name}</b>{p.id === currentUserId() ? " ✓" : ""}<br />
                <span className="small muted">{p.tagline} · {p.city}</span>
              </span>
            </button>
          ))}
          <button role="menuitem" className="btn btn-ghost btn-block" style={{ justifyContent: "flex-start" }} onClick={() => switchTo(null)}>
            Continue as a guest
          </button>
        </div>
      )}
    </div>
  );
}

export function Layout({ children, chat }: { children: ReactNode; chat?: ReactNode }) {
  const { data: me } = useMe();
  return (
    <div className="app">
      <header className="header">
        <NavLink to="/" className="brand" aria-label="Walk-In Wardrobe home">
          <img src="/favicon.svg" alt="" className="brand-mark" />
          <span>Walk-In Wardrobe</span>
        </NavLink>
        <nav className="nav" aria-label="Main">
          {NAV.map((n) => <NavLink key={n.to} to={n.to} end={n.to === "/"}>{n.label}</NavLink>)}
        </nav>
        <div className="header-spacer" />
        <div className="header-actions">
          <NavLink to="/notifications" className="icon-btn" aria-label={`Notifications${me?.unread_notifications ? `, ${me.unread_notifications} unread` : ""}`}>
            <Icon name="bell" />
            {!!me?.unread_notifications && <span className="badge">{me.unread_notifications}</span>}
          </NavLink>
          <NavLink to="/cart" className="icon-btn" aria-label={`Cart${me?.cart_count ? `, ${me.cart_count} items` : ""}`}>
            <Icon name="bag" />
            {!!me?.cart_count && <span className="badge">{me.cart_count}</span>}
          </NavLink>
          <PersonaMenu />
        </div>
      </header>
      <div className={`shell ${chat ? "with-chat" : ""}`}>
        <main className="main" id="main">{children}</main>
        {chat}
      </div>
      <nav className="bottom-nav" aria-label="Main">
        {NAV.filter((n) => n.mobile).map((n) => (
          <NavLink key={n.to} to={n.to} end={n.to === "/"}><Icon name={n.icon} />{n.label}</NavLink>
        ))}
      </nav>
    </div>
  );
}

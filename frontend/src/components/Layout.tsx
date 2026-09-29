import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ReactNode, useEffect, useRef, useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { api, currentUserId, setCurrentUserId } from "../api";
import type { Me, Vocab } from "../types";
import { Icon } from "./ui";

export function useMe() {
  return useQuery({ queryKey: ["me"], queryFn: () => api.get<Me>("/me"), enabled: !!currentUserId() });
}

export function useVocab() {
  return useQuery({ queryKey: ["vocab"], queryFn: () => api.get<Vocab>("/vocab"), staleTime: Infinity });
}

export type NavItem = { to: string; label: string; icon: string };

export const NAV: NavItem[] = [
  { to: "/", label: "Wardrobes", icon: "hanger" },
  { to: "/shop", label: "Shop", icon: "tag" },
  { to: "/taste", label: "My taste", icon: "sparkle" },
  { to: "/preferences", label: "Preferences", icon: "sliders" },
];

function ProfileMenu() {
  const qc = useQueryClient();
  const nav = useNavigate();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const { data: me } = useMe();

  useEffect(() => {
    const h = (e: MouseEvent) => ref.current && !ref.current.contains(e.target as Node) && setOpen(false);
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, []);

  const startOver = () => {
    if (!confirm("Start over with a new profile on this device? Your current wardrobe stays saved but you'll be signed out of it.")) return;
    setCurrentUserId(null);
    setOpen(false);
    qc.clear();
    nav("/welcome");
  };

  const deleteMe = async () => {
    if (!confirm("Delete your profile, folders, hangers, cart and orders? This can't be undone.")) return;
    await api.del("/me");
    setCurrentUserId(null);
    qc.clear();
    nav("/welcome");
  };

  return (
    <div ref={ref} style={{ position: "relative" }}>
      <button className="btn btn-sm btn-ghost" onClick={() => setOpen((o) => !o)} aria-haspopup="menu" aria-expanded={open}>
        <span aria-hidden style={{ width: 26, height: 26, borderRadius: 99, background: "#e3d9cb", display: "grid", placeItems: "center", fontFamily: "var(--serif)" }}>
          {me?.name?.[0]?.toUpperCase() ?? "·"}
        </span>
        <span className="persona-name">{me?.name ?? "…"}</span>
      </button>
      {open && (
        <div role="menu" className="card" style={{ position: "absolute", right: 0, top: 46, width: 240, padding: 6, zIndex: 50 }}>
          <div style={{ padding: "8px 10px" }}><b>{me?.name}</b><div className="small muted">{me?.city}</div></div>
          <button role="menuitem" className="btn btn-ghost btn-block" style={{ justifyContent: "flex-start" }}
            onClick={() => { setOpen(false); nav("/preferences"); }}>Edit profile & preferences</button>
          <button role="menuitem" className="btn btn-ghost btn-block" style={{ justifyContent: "flex-start" }}
            onClick={() => { setOpen(false); nav("/cart"); }}>Cart & orders</button>
          <button role="menuitem" className="btn btn-ghost btn-block" style={{ justifyContent: "flex-start" }} onClick={startOver}>
            Start over as someone new
          </button>
          <button role="menuitem" className="btn btn-ghost btn-block" style={{ justifyContent: "flex-start", color: "var(--rose)" }} onClick={deleteMe}>
            Delete my profile & data
          </button>
        </div>
      )}
    </div>
  );
}

export function Layout({ children, chat, bare = false }: { children: ReactNode; chat?: ReactNode; bare?: boolean }) {
  const { data: me } = useMe();
  return (
    <div className="app">
      <header className="header">
        <NavLink to="/" className="brand" aria-label="Walk-In Wardrobe home">
          <img src="/favicon.svg" alt="" className="brand-mark" />
          <span>Walk-In Wardrobe</span>
        </NavLink>
        {!bare && (
          <nav className="nav" aria-label="Main">
            {NAV.map((n) => <NavLink key={n.to} to={n.to} end={n.to === "/"}>{n.label}</NavLink>)}
          </nav>
        )}
        <div className="header-spacer" />
        {!bare && (
          <div className="header-actions">
            <NavLink to="/notifications" className="icon-btn" aria-label={`Notifications${me?.unread_notifications ? `, ${me.unread_notifications} unread` : ""}`}>
              <Icon name="bell" />
              {!!me?.unread_notifications && <span className="badge">{me.unread_notifications}</span>}
            </NavLink>
            <NavLink to="/cart" className="icon-btn" aria-label={`Cart${me?.cart_count ? `, ${me.cart_count} items` : ""}`}>
              <Icon name="bag" />
              {!!me?.cart_count && <span className="badge">{me.cart_count}</span>}
            </NavLink>
            <ProfileMenu />
          </div>
        )}
      </header>
      <div className={`shell ${chat ? "with-chat" : ""}`}>
        <main className="main" id="main">{children}</main>
        {chat}
      </div>
      {!bare && (
        <nav className="bottom-nav" aria-label="Main">
          {NAV.map((n) => <NavLink key={n.to} to={n.to} end={n.to === "/"}><Icon name={n.icon} />{n.label}</NavLink>)}
        </nav>
      )}
    </div>
  );
}

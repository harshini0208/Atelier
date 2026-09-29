import "@fontsource/fraunces/400.css";
import "@fontsource/fraunces/500.css";
import "@fontsource/inter/400.css";
import "@fontsource/inter/600.css";
import "@fontsource/inter/700.css";
import "./styles.css";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode, Suspense } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Link, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { currentUserId } from "./api";
import ChatPanel from "./components/ChatPanel";
import { Layout } from "./components/Layout";
import { Loading, ToastProvider } from "./components/ui";
import Admin from "./pages/Admin";
import Cart from "./pages/Cart";
import FolderPage from "./pages/FolderPage";
import Home from "./pages/Home";
import InspoReview from "./pages/InspoReview";
import Notifications from "./pages/Notifications";
import Onboarding from "./pages/Onboarding";
import Preferences from "./pages/Preferences";
import Shop from "./pages/Shop";
import StyleBoard from "./pages/StyleBoard";
import Taste from "./pages/Taste";

const qc = new QueryClient({ defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false, staleTime: 15_000 } } });

function NotFound() {
  return (
    <div className="empty">
      <h3>That page isn't in the wardrobe</h3>
      <Link to="/" className="btn btn-primary" style={{ marginTop: 12 }}>Back to your wardrobes</Link>
    </div>
  );
}

function App() {
  const { pathname } = useLocation();
  const signedIn = !!currentUserId();
  if (pathname === "/admin") return <Layout bare><Admin /></Layout>;
  if (!signedIn && pathname !== "/welcome") return <Navigate to="/welcome" replace />;
  if (pathname === "/welcome") return signedIn ? <Navigate to="/" replace /> : <Layout bare><Onboarding /></Layout>;
  return (
    <Layout chat={<ChatPanel />}>
      <Suspense fallback={<Loading />}>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/shop" element={<Shop />} />
          <Route path="/preferences" element={<Preferences />} />
          <Route path="/folders/:id" element={<FolderPage />} />
          <Route path="/folders/:id/board" element={<StyleBoard />} />
          <Route path="/inspo/:id" element={<InspoReview />} />
          <Route path="/cart" element={<Cart />} />
          <Route path="/taste" element={<Taste />} />
          <Route path="/notifications" element={<Notifications />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </Suspense>
    </Layout>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={qc}>
      <ToastProvider>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </ToastProvider>
    </QueryClientProvider>
  </StrictMode>,
);

import "@fontsource/fraunces/400.css";
import "@fontsource/fraunces/500.css";
import "@fontsource/inter/400.css";
import "@fontsource/inter/600.css";
import "@fontsource/inter/700.css";
import "./styles.css";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode, Suspense } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Link, Route, Routes } from "react-router-dom";
import ChatPanel from "./components/ChatPanel";
import { Layout } from "./components/Layout";
import { Loading, ToastProvider } from "./components/ui";
import FolderPage from "./pages/FolderPage";
import Home from "./pages/Home";
import InspoReview from "./pages/InspoReview";
import Preferences from "./pages/Preferences";
import Wardrobe from "./pages/Wardrobe";
import Cart from "./pages/Cart";
import Notifications from "./pages/Notifications";

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
  return (
    <Layout chat={<ChatPanel />}>
      <Suspense fallback={<Loading />}>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/preferences" element={<Preferences />} />
          <Route path="/folders/:id" element={<FolderPage />} />
          <Route path="/folders/:id/wardrobe" element={<Wardrobe />} />
          <Route path="/inspo/:id" element={<InspoReview />} />
          <Route path="/cart" element={<Cart />} />
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

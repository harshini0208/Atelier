import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  Outlet,
  Link,
  createRootRouteWithContext,
  useRouter,
  HeadContent,
  type ErrorComponentProps,
} from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { useRouterState, useNavigate } from "@tanstack/react-router";
import { Toaster } from "@/components/ui/sonner";
import { AppShell } from "@/components/wiw/AppShell";
import { applyTheme, loadSession, savedTheme, useStore } from "@/lib/store";
import { currentUserId } from "@/lib/api";

function NotFoundComponent() {
  return (
    <div className="flex min-h-[60vh] items-center justify-center px-4">
      <div className="max-w-md text-center">
        <h1 className="display text-6xl">404</h1>
        <h2 className="mt-4 text-xl font-semibold">Page not found</h2>
        <p className="mt-2 text-sm text-muted-foreground">The page you're looking for doesn't exist or has been moved.</p>
        <div className="mt-6">
          <Link to="/" className="inline-flex h-11 items-center justify-center rounded-full bg-primary px-5 text-sm font-medium text-primary-foreground">
            Go home
          </Link>
        </div>
      </div>
    </div>
  );
}

function ErrorComponent({ error, reset }: ErrorComponentProps) {
  console.error(error);
  const router = useRouter();
  return (
    <div className="flex min-h-[60vh] items-center justify-center px-4">
      <div className="max-w-md text-center">
        <h1 className="text-xl font-semibold tracking-tight">This page didn't load</h1>
        <p className="mt-2 text-sm text-muted-foreground">{error instanceof Error ? error.message : "Something went wrong."}</p>
        <div className="mt-6 flex flex-wrap justify-center gap-2">
          <button
            onClick={() => {
              void router.invalidate();
              reset();
            }}
            className="inline-flex h-11 items-center justify-center rounded-full bg-primary px-5 text-sm font-medium text-primary-foreground"
          >
            Try again
          </button>
          <a href="/" className="inline-flex h-11 items-center justify-center rounded-full border border-border bg-card px-5 text-sm font-medium">
            Go home
          </a>
        </div>
      </div>
    </div>
  );
}

export const Route = createRootRouteWithContext<{ queryClient: QueryClient }>()({
  head: () => ({ meta: [{ title: "Atelier · Urban Thread" }] }),
  component: RootComponent,
  notFoundComponent: NotFoundComponent,
  errorComponent: ErrorComponent,
});

function RootComponent() {
  const { queryClient } = Route.useRouteContext();
  return (
    <QueryClientProvider client={queryClient}>
      <HeadContent />
      <Session />
      <Toaster />
    </QueryClientProvider>
  );
}

/** Pages without the shopper shell: onboarding and the brand tools. */
const BARE = new Set(["/welcome", "/admin"]);

function Session() {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const navigate = useNavigate();
  const ready = useStore((s) => s.ready);
  const [checked, setChecked] = useState(false);
  const bare = BARE.has(pathname);

  useEffect(() => {
    applyTheme(savedTheme());
    if (bare) return;
    if (!currentUserId()) {
      void navigate({ to: "/welcome" });
      return;
    }
    setChecked(true);
    void loadSession();
  }, [bare, navigate]);

  if (bare) return <Outlet />;
  return (
    <AppShell>
      {checked && ready ? (
        <Outlet />
      ) : (
        <div className="space-y-6" aria-busy="true">
          <div className="shimmer h-12 w-2/3 rounded-[16px]" />
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            {[0, 1, 2, 3].map((i) => (
              <div key={i} className="shimmer aspect-[3/4] rounded-[18px]" />
            ))}
          </div>
        </div>
      )}
    </AppShell>
  );
}

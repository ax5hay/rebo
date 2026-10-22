import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { lazy, StrictMode, Suspense } from "react";
import { createRoot } from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router";
import Shell from "./shell";
import AskPage from "./pages/ask";
// Everything but Ask is loaded when first opened (charts, editors, admin screens).
const KnowledgePage = lazy(() => import("./pages/knowledge"));
const ReviewPage = lazy(() => import("./pages/review"));
const AdminPage = lazy(() => import("./pages/admin"));
const ConfigPage = lazy(() => import("./pages/config"));
const InsightsPage = lazy(() => import("./pages/insights"));
const MePage = lazy(() => import("./pages/me"));
const HelpPage = lazy(() => import("./pages/help"));
const AboutPage = lazy(() => import("./pages/about"));
const later = (page: React.ReactNode) => <Suspense fallback={<p className="empty">Loading…</p>}>{page}</Suspense>;
import "./styles.css";

const queries = new QueryClient({ defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } } });

const router = createBrowserRouter(
  [
    {
      path: "/",
      element: <Shell />,
      children: [
        { index: true, element: <AskPage /> },
        { path: "c/:conversationId", element: <AskPage /> },
        { path: "knowledge", element: later(<KnowledgePage />) },
        { path: "review", element: later(<ReviewPage />) },
        { path: "admin", element: later(<AdminPage />) },
        { path: "config", element: later(<ConfigPage />) },
        { path: "insights", element: later(<InsightsPage />) },
        { path: "me", element: later(<MePage />) },
        { path: "help", element: later(<HelpPage />) },
        { path: "about", element: later(<AboutPage />) },
      ],
    },
  ],
  { basename: "/app" },
);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queries}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </StrictMode>,
);

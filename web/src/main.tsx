import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { lazy, StrictMode, Suspense } from "react";
import { createRoot } from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router";
import Shell from "./shell";
import AskPage from "./pages/ask";
import KnowledgePage from "./pages/knowledge";
import ReviewPage from "./pages/review";
import AdminPage from "./pages/admin";
import ConfigPage from "./pages/config";
const InsightsPage = lazy(() => import("./pages/insights"));  // charts: loaded only when opened
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
        { path: "knowledge", element: <KnowledgePage /> },
        { path: "review", element: <ReviewPage /> },
        { path: "admin", element: <AdminPage /> },
        { path: "config", element: <ConfigPage /> },
        { path: "insights", element: <Suspense fallback={<p className="empty">Loading…</p>}><InsightsPage /></Suspense> },
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

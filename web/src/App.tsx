import { lazy, Suspense } from "react";
import { createBrowserRouter, Navigate } from "react-router-dom";
import { Layout } from "./app/Layout";

// Route-level code splitting: each page is its own chunk, fetched on navigation.
const Login = lazy(() => import("./pages/Login"));
const Dashboard = lazy(() => import("./pages/Dashboard"));
const Wiki = lazy(() => import("./pages/Wiki"));
const Achievements = lazy(() => import("./pages/Achievements"));
const Learn = lazy(() => import("./pages/Learn"));
const Canon = lazy(() => import("./pages/Canon"));
const Portfolio = lazy(() => import("./pages/Portfolio"));
const Analyze = lazy(() => import("./pages/Analyze"));
const Doc = lazy(() => import("./pages/Doc"));
const Stub = lazy(() => import("./pages/Stub"));

const Loading = () => <div style={{ padding: "40px 0", color: "var(--muted)", fontSize: 14 }}>加载中…</div>;

export const router = createBrowserRouter([
  { path: "/login", element: <Suspense fallback={<Loading />}><Login /></Suspense> },
  {
    element: <Layout />,
    children: [
      { path: "/", element: <Dashboard /> },
      { path: "/dashboard", element: <Navigate to="/" replace /> },
      { path: "/wiki", element: <Wiki /> },
      { path: "/achievements", element: <Achievements /> },
      { path: "/learn", element: <Learn /> },
      { path: "/canon", element: <Canon /> },
      { path: "/portfolio", element: <Portfolio /> },
      { path: "/analyze", element: <Analyze /> },
      { path: "/doc/*", element: <Doc /> },
      { path: "*", element: <Stub /> },
    ],
  },
], { future: { v7_relativeSplatPath: true } });

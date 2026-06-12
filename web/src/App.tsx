import { createBrowserRouter, Navigate } from "react-router-dom";
import { Layout } from "./app/Layout";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Stub from "./pages/Stub";

// Pages migrate to React incrementally; not-yet-migrated routes render a Stub.
export const router = createBrowserRouter([
  { path: "/login", element: <Login /> },
  {
    element: <Layout />,
    children: [
      { path: "/", element: <Dashboard /> },
      { path: "/dashboard", element: <Navigate to="/" replace /> },
      { path: "/portfolio", element: <Stub /> },
      { path: "/canon", element: <Stub /> },
      { path: "/wiki", element: <Stub /> },
      { path: "/analyze", element: <Stub /> },
      { path: "/achievements", element: <Stub /> },
      { path: "/learn", element: <Stub /> },
      { path: "/doc/*", element: <Stub /> },
      { path: "*", element: <Stub /> },
    ],
  },
], { future: { v7_relativeSplatPath: true } });

import { createBrowserRouter, Navigate } from "react-router-dom";
import { Layout } from "./app/Layout";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Wiki from "./pages/Wiki";
import Achievements from "./pages/Achievements";
import Learn from "./pages/Learn";
import Canon from "./pages/Canon";
import Stub from "./pages/Stub";

// Pages migrate to React incrementally; not-yet-migrated routes render a Stub.
export const router = createBrowserRouter([
  { path: "/login", element: <Login /> },
  {
    element: <Layout />,
    children: [
      { path: "/", element: <Dashboard /> },
      { path: "/dashboard", element: <Navigate to="/" replace /> },
      { path: "/wiki", element: <Wiki /> },
      { path: "/achievements", element: <Achievements /> },
      { path: "/learn", element: <Learn /> },
      { path: "/canon", element: <Canon /> },
      { path: "/portfolio", element: <Stub /> },
      { path: "/analyze", element: <Stub /> },
      { path: "/doc/*", element: <Stub /> },
      { path: "*", element: <Stub /> },
    ],
  },
], { future: { v7_relativeSplatPath: true } });

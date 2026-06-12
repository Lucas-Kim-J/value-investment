import { Suspense } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { motion } from "framer-motion";
import { Nav } from "./Nav";
import { ShellProvider } from "../shell/ShellContext";

const Loading = () => <div style={{ padding: "40px 0", color: "var(--muted)", fontSize: 14 }}>加载中…</div>;

export function Layout() {
  const loc = useLocation();
  return (
    <ShellProvider>
      <div className="app-wrap">
        <Nav />
        <motion.main
          key={loc.pathname}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
        >
          <Suspense fallback={<Loading />}>
            <Outlet />
          </Suspense>
        </motion.main>
      </div>
    </ShellProvider>
  );
}

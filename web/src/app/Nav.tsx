import { NavLink } from "react-router-dom";
import { useMe } from "../lib/hooks";
import { useShell } from "../shell/ShellContext";

const ITEMS: ReadonlyArray<readonly [string, string]> = [
  ["/", "🏠 首页"],
  ["/learn", "📖 学习"],
  ["/canon", "📚 一手内容"],
  ["/wiki", "🔍 术语"],
  ["/portfolio", "💼 我的持仓"],
  ["/analyze", "🏢 公司分析"],
  ["/market", "🌐 市场"],
  ["/signals", "📡 信号"],
  ["/achievements", "🏅 成就"],
];

export function Nav() {
  const user = useMe();
  const { openCmdk } = useShell();
  return (
    <nav className="vi-nav">
      {ITEMS.map(([to, label]) => (
        <NavLink key={to} to={to} end={to === "/"} className={({ isActive }) => (isActive ? "active" : "")}>
          {label}
        </NavLink>
      ))}
      <span className="sp" />
      <span className="kbtn" onClick={openCmdk}>
        🔍 术语速查 <kbd>⌘K</kbd>
      </span>
      {user && (
        <span className="who">
          👤 <b>{user}</b>
        </span>
      )}
    </nav>
  );
}

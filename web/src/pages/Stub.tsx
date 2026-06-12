import { useLocation } from "react-router-dom";

/** Placeholder for pages not yet migrated to React (incremental migration). */
export default function Stub() {
  const loc = useLocation();
  return (
    <div className="app-head">
      <div className="eyebrow">迁移中</div>
      <h1>🚧 这一页正在搬到 React</h1>
      <p>
        <code>{loc.pathname}</code> 还在迁移。其余功能照常——这是 v4-react 增量迁移的占位页。
      </p>
    </div>
  );
}

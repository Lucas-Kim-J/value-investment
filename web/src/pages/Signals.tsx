import { useEffect, useState } from "react";
import { apiGet } from "../lib/api";
import { useMe } from "../lib/hooks";
import type { Signal, SignalDetail } from "../lib/types";

// source-type tabs = the 板块 structure. v1 wires only 播客.
const TABS = [
  { key: "podcast", label: "🎧 播客", soon: false },
  { key: "news", label: "📰 消息面 · 金十", soon: true },
  { key: "twitter", label: "🐦 推特", soon: true },
  { key: "data", label: "📊 数据", soon: true },
];
const XYZ_LOGO = "/logos/xiaoyuzhou.png";

function fmtDate(s?: string | null): string {
  if (!s) return "";
  const d = new Date(s);
  return Number.isNaN(d.getTime()) ? "" : `${d.getMonth() + 1}/${d.getDate()}`;
}

function Card({ sig }: { sig: Signal }) {
  const [open, setOpen] = useState(false);
  const [transcript, setTranscript] = useState<string | null>(null);
  const [showTrx, setShowTrx] = useState(false);
  const c = sig.card;

  async function toggleTranscript() {
    setShowTrx((v) => !v);
    if (transcript === null) {
      const r = await apiGet<SignalDetail>(`/api/signals/${sig.external_id}`);
      setTranscript(r.data?.transcript ?? "（该集暂无转录）");
    }
  }

  return (
    <div className={`sig${open ? " open" : ""}`}>
      <div className="sig-top" onClick={() => setOpen((v) => !v)}>
        <img className="thumb" src={sig.image_url || XYZ_LOGO} alt="" />
        <div className="sig-main">
          <h3 className="ttl">{sig.title}</h3>
          <div className="sig-meta">
            <span className="pill">{c.pillar || "—"}</span>
            <span>{fmtDate(sig.published_at)}</span>
          </div>
          <p className="sig-snip"><b>主旨</b>:{c.tldr || "—"}</p>
        </div>
        <span className="chev">▾</span>
      </div>
      {open && (
        <div className="sig-body">
          <p className="fld"><span className="k">非共识</span>{c.non_consensus || "—"}</p>
          <p className="fld"><span className="k">给你的新角度</span>{c.new_angle || "—"}</p>
          <p className="fld warn"><span className="k">⚠️ 该警惕什么</span>{c.caution || "—"}</p>
          <p className="relisten">回听原集:<b>{c.worth_relisten?.yes ? "是" : "否"}</b>
            {c.worth_relisten?.timestamps?.length ? `（${c.worth_relisten.timestamps.join("、")}）` : ""}</p>
          <div className="acts">
            <a className="btn" href={sig.url} target="_blank" rel="noreferrer">🔗 到小宇宙听原集</a>
            <button className="btn" onClick={toggleTranscript}>📄 转录全文 ▾</button>
          </div>
          {showTrx && (
            <div className="trx">
              <span className="note">机器转录(faster-whisper),可能有错字。</span>
              {transcript ?? "加载中…"}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

type ShowGroup = { title: string; image?: string | null; items: Signal[] };

// Group cards by 栏目 (show), preserving the incoming order (API sorts newest-first,
// so the most-recently-updated show floats to the top).
function groupByShow(list: Signal[]): ShowGroup[] {
  const groups: ShowGroup[] = [];
  const idx = new Map<string, number>();
  for (const it of list) {
    const t = it.show_title || "未知来源";
    let i = idx.get(t);
    if (i === undefined) {
      i = groups.length;
      idx.set(t, i);
      groups.push({ title: t, image: it.image_url, items: [] });
    }
    groups[i].items.push(it);
  }
  return groups;
}

export default function Signals() {
  const user = useMe();
  const [items, setItems] = useState<Signal[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [active, setActive] = useState<string | null>(null); // null = 全部

  useEffect(() => {
    apiGet<{ items: Signal[] }>("/api/signals").then((r) => {
      setItems(r.data?.items ?? []);
      setLoaded(true);
    });
  }, []);

  const allShows = groupByShow(items);            // stable chip order + per-show counts
  const visible = active ? items.filter((i) => (i.show_title || "未知来源") === active) : items;
  const groups = groupByShow(visible);

  return (
    <>
      <div className="app-head">
        <div className="eyebrow">VALUE INVESTING · 信号流</div>
        <h1>📡 信号</h1>
        <p>把各处信号源替你过滤,只留<b>非共识</b>的部分——你花的是读 signal 的时间,不是刷信息的时间。</p>
      </div>

      <div className="sig-tabs">
        {TABS.map((t) => (
          <span key={t.key} className={`sig-tab${t.soon ? " soon" : " active"}`}>
            {t.label}{t.soon && <i>即将</i>}
          </span>
        ))}
      </div>

      {items.length > 0 && (
        <div className="sig-shows">
          <button className={`show-chip all${active === null ? " on" : ""}`} onClick={() => setActive(null)}>
            全部<span className="sc-n">{items.length}</span>
          </button>
          {allShows.map((s) => (
            <button
              key={s.title}
              className={`show-chip${active === s.title ? " on" : ""}`}
              onClick={() => setActive(s.title)}
            >
              <img src={s.image || XYZ_LOGO} alt="" />
              <span className="sc-t">{s.title}</span>
              <span className="sc-n">{s.items.length}</span>
            </button>
          ))}
        </div>
      )}

      {user === null && <p className="status">登录后查看信号。</p>}
      {loaded && items.length === 0 && user && (
        <p className="status">还没有信号卡——管道每天 08:00 自动更新。</p>
      )}

      {groups.map((g) => (
        <section className="sig-group" key={g.title}>
          <div className="sig-lane">
            <img className="logo" src={g.image || XYZ_LOGO} alt="" />
            <span className="lane-t">{g.title}</span>
            <img className="plat" src={XYZ_LOGO} alt="小宇宙" />
            <span className="lane-s">· {g.items.length} 条 · 每天 08:00 自动更新</span>
          </div>
          <div className="sig-list">
            {g.items.map((s) => <Card key={s.external_id} sig={s} />)}
          </div>
        </section>
      ))}
    </>
  );
}

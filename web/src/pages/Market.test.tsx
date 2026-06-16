import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

const board = {
  market: "美股",
  temperature: { note: "综合估值与广度看市场温度", hot: false },
  valuation: { percentile: 97.7, level: 4, label: "极贵", note: "估值天花板——远期回报受限",
               pe: { value: 28.1, percentile: 97.7 }, cape: { value: 42.2, percentile: 99 } },
  concentration: { top_n_weight: 32, herfindahl: 205, rsp_spy_percentile: 35, top_n: 7,
                   concentrated: true, label: "高度集中（少数大票主导）", detail: "前7大权重 32%；HHI 205" },
  breadth: { pct_above_200: 64.1, pct_above_50: 68.1, level: 3, label: "广度中性", healthy: true, n: 501 },
  sectors: [
    { ticker: "SMH", name: "半导体", quadrant: "领先", heat: 51, rs_6m: 58, rs_3m: 44 },
    { ticker: "XLC", name: "通信", quadrant: "落后", heat: -13.3, rs_6m: -13, rs_3m: -14 },
  ],
  crowding_note: "拥挤=代理，非实测仓位。",
  warnings: [],
};
const cycle = {
  market: "美股",
  composite: { score: 1.56, level: 5, position: "扩张 / risk-on", tailwind: "顺风",
               sahm_breaker: false, lenses_used: [], lenses_missing: [] },
  lenses: [{ key: "yield_curve", title: "利率/衰退", score: 1, label: "曲线正常陡峭", detail: "10Y-3M=+0.87pp" }],
  asset_tilt: { 成长股: "✓" }, cape_flag: { on: true, note: "估值处历史 99% 分位" },
  recession_prob: 10.6, fred_enabled: true, warnings: [],
};

vi.mock("../lib/api", () => ({
  apiGet: vi.fn((p: string) =>
    p.startsWith("/api/market/board")
      ? Promise.resolve({ ok: true, status: 200, data: board })
      : Promise.resolve({ ok: true, status: 200, data: cycle })),
}));
vi.mock("../lib/hooks", () => ({ useMe: () => "lucas" }));

import Market from "./Market";

describe("Market", () => {
  beforeEach(() => vi.clearAllMocks());

  it("renders 体温计 + 板块热力图 + 周期罗盘", async () => {
    render(<MemoryRouter><Market /></MemoryRouter>);
    expect(await screen.findByText("极贵")).toBeInTheDocument();          // 估值体温计
    expect(screen.getByText(/高度集中/)).toBeInTheDocument();             // 集中度
    expect(screen.getByText("广度中性")).toBeInTheDocument();             // 广度
    expect(screen.getByText("半导体")).toBeInTheDocument();               // 板块热力图
    expect(screen.getByText("扩张 / risk-on")).toBeInTheDocument();       // 周期罗盘
  });
});

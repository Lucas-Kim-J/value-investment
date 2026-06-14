import type { EChartsCoreOption } from "echarts/core";
import type { CompanySnapshot } from "../../lib/types";

/** read a CSS custom property so charts follow the light/dark theme */
export const cssVar = (n: string) =>
  getComputedStyle(document.documentElement).getPropertyValue(n).trim() || "#888";

// ---- formatters ----
export function fmtMoney(v: number | null | undefined, cur?: string | null): string | null {
  if (v == null) return null;
  const sym = cur === "USD" ? "$" : cur === "CNY" ? "¥" : cur === "HKD" ? "HK$" : "";
  const a = Math.abs(v);
  if (a >= 1e12) return sym + (v / 1e12).toFixed(2) + "T";
  if (a >= 1e9) return sym + (v / 1e9).toFixed(2) + "B";
  if (a >= 1e6) return sym + (v / 1e6).toFixed(2) + "M";
  return sym + v.toFixed(0);
}
export const fmtX = (v?: number | null) => (v == null ? null : v.toFixed(1) + "×");
export const fmtPct = (v?: number | null) => (v == null ? null : v.toFixed(1) + "%");
export const fmtPx = (v?: number | null, cur?: string | null) =>
  v == null ? null : (cur === "USD" ? "$" : "") + v.toFixed(2);

export function relTime(iso?: string): string {
  if (!iso) return "";
  const t = new Date(iso);
  if (isNaN(t.getTime())) return "";
  const s = (Date.now() - t.getTime()) / 1000;
  if (s < 60) return "刚刚";
  if (s < 3600) return Math.floor(s / 60) + " 分钟前";
  if (s < 86400) return Math.floor(s / 3600) + " 小时前";
  return Math.floor(s / 86400) + " 天前";
}

const axisStyle = () => {
  const b = cssVar("--border"), mu = cssVar("--muted");
  return {
    axisLine: { lineStyle: { color: b } },
    axisLabel: { color: mu, fontSize: 11 },
    splitLine: { lineStyle: { color: b, opacity: 0.5 } },
  };
};

// ---- option builders ----
export function radarOption(r: CompanySnapshot["radar"]): EChartsCoreOption | null {
  const inds = r?.indicators || [];
  if (!inds.length) return null;
  const accent = cssVar("--accent"), mu = cssVar("--muted"), notes = r.notes || {};
  const raw = r.values || [];
  return {
    tooltip: {
      backgroundColor: cssVar("--bg-soft"),
      borderColor: cssVar("--border"),
      textStyle: { color: cssVar("--fg"), fontSize: 12 },
      formatter: () =>
        inds
          .map(
            (it, i) =>
              `${it.name}：<b>${raw[i] == null ? "数据缺失" : raw[i]}</b><br><span style="color:${mu};font-size:11px">${notes[it.name] || ""}</span>`,
          )
          .join("<br>"),
    },
    radar: {
      indicator: inds,
      radius: "66%",
      center: ["50%", "54%"],
      axisName: { color: cssVar("--fg-soft"), fontSize: 12 },
      splitLine: { lineStyle: { color: cssVar("--border") } },
      splitArea: { areaStyle: { color: ["transparent"] } },
      axisLine: { lineStyle: { color: cssVar("--border") } },
    },
    series: [
      {
        type: "radar",
        data: [
          {
            value: raw.map((v) => (v == null ? 0 : v)),
            name: "健康度",
            areaStyle: { color: accent, opacity: 0.18 },
            lineStyle: { color: accent, width: 2 },
            itemStyle: { color: accent },
          },
        ],
      },
    ],
  };
}

export function trendOption(f: CompanySnapshot["financials"]): EChartsCoreOption | null {
  const yrs = f?.years || [];
  if (!yrs.length) return null;
  const accent = cssVar("--accent"), good = cssVar("--good"), as = axisStyle();
  const bil = (v: number | null) => (v == null ? null : +(v / 1e9).toFixed(2));
  return {
    tooltip: {
      trigger: "axis",
      backgroundColor: cssVar("--bg-soft"),
      borderColor: cssVar("--border"),
      textStyle: { color: cssVar("--fg"), fontSize: 12 },
    },
    legend: { data: ["营收", "净利润", "净利率"], textStyle: { color: cssVar("--muted"), fontSize: 11 }, top: 0 },
    grid: { left: 50, right: 46, top: 30, bottom: 26 },
    xAxis: { type: "category", data: yrs, ...as },
    yAxis: [
      { type: "value", name: "十亿", nameTextStyle: { color: cssVar("--muted"), fontSize: 10 }, ...as },
      {
        type: "value",
        name: "%",
        nameTextStyle: { color: cssVar("--muted"), fontSize: 10 },
        axisLabel: { color: cssVar("--muted"), fontSize: 11, formatter: "{value}%" },
        splitLine: { show: false },
        axisLine: { lineStyle: { color: cssVar("--border") } },
      },
    ],
    series: [
      { name: "营收", type: "bar", data: (f.revenue || []).map(bil), itemStyle: { color: accent, opacity: 0.85 }, barMaxWidth: 26 },
      { name: "净利润", type: "bar", data: (f.net_income || []).map(bil), itemStyle: { color: good, opacity: 0.8 }, barMaxWidth: 26 },
      {
        name: "净利率",
        type: "line",
        yAxisIndex: 1,
        data: f.net_margin || [],
        smooth: true,
        lineStyle: { color: cssVar("--fg-soft"), width: 2 },
        itemStyle: { color: cssVar("--fg-soft") },
      },
    ],
  };
}

export function priceOption(h: CompanySnapshot["price_history"], cur?: string | null): EChartsCoreOption | null {
  const dates = h?.dates || [], close = h?.close || [];
  if (!dates.length) return null;
  const accent = cssVar("--accent"), as = axisStyle();
  return {
    tooltip: {
      trigger: "axis",
      backgroundColor: cssVar("--bg-soft"),
      borderColor: cssVar("--border"),
      textStyle: { color: cssVar("--fg"), fontSize: 12 },
      valueFormatter: (v: unknown) => (v == null ? "-" : (cur === "USD" ? "$" : "") + (+(v as number)).toFixed(2)),
    },
    grid: { left: 48, right: 18, top: 18, bottom: 28 },
    xAxis: { type: "category", data: dates, boundaryGap: false, ...as, axisLabel: { color: cssVar("--muted"), fontSize: 10 } },
    yAxis: { type: "value", scale: true, ...as },
    series: [
      {
        type: "line",
        data: close,
        smooth: true,
        showSymbol: false,
        lineStyle: { color: accent, width: 2 },
        areaStyle: { color: cssVar("--accent-soft") },
      },
    ],
  };
}

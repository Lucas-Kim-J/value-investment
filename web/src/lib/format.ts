/** Display helpers shared across pages. */

/**
 * Human "as-of" label for a cached snapshot, from the server-computed `_age_s`
 * (seconds since fetch; absent on a just-fetched response → treated as fresh).
 * Mirrors the buckets of `analyze/charts.relTime`, but takes seconds directly.
 */
export function dataFreshness(ageSeconds?: number): string {
  const s = ageSeconds ?? 0;
  if (s < 60) return "数据刚刚更新";
  if (s < 3600) return `数据更新于 ${Math.floor(s / 60)} 分钟前`;
  if (s < 86400) return `数据更新于 ${Math.floor(s / 3600)} 小时前`;
  return `数据更新于 ${Math.floor(s / 86400)} 天前`;
}

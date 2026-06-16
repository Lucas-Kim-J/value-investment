export type Stage = "novice" | "building" | "practitioner";

export interface LearningStats {
  holdings: number;
  canon_read: number;
  canon_noted: number;
  term_mastered: number;
  company_analyzed: number;
  markets_analyzed: number;
  report_generated: number;
  total_min: number;
}

export interface LearningSummary {
  stage: Stage;
  canon_read: number;
  term_mastered: number;
  total_hours: number;
  stats: LearningStats;
}

export interface Achievement {
  key: string;
  title: string;
  description: string;
  icon: string;
  unlocked: boolean;
  unlocked_at?: string | null;
}

export interface AchievementsResp {
  items: Achievement[];
  unlocked_count: number;
}

export interface CanonItem {
  slug: string;
  title: string;
  tier: string;
  kind: string;
  source?: string;
  period?: string;
  est_minutes: number;
  why?: string;
  read?: boolean;
}

export interface CanonEvent {
  action: string;
  detail?: { note?: string };
  created_at?: string;
}

export interface CanonDetail extends CanonItem {
  official_url?: string | null;
  guide?: string;
  questions?: string[];
  related_terms?: string[];
  my_events?: CanonEvent[];
  error?: string;
}

export interface Holding {
  market: string;
  ticker: string;
  name: string;
  buy_date: string | null;
  cost: number | null;
  position_pct: number | null;
  note: string;
}

export interface GlossaryTerm {
  slug: string;
  term: string;
  term_en?: string;
  category?: string;
  definition?: string;
  mastery?: "" | "seen" | "mastered";
  learned?: boolean;
}

export interface TermDetail extends GlossaryTerm {
  detail_url?: string | null;
  related?: string[];
  appears_in?: { slug: string; title: string }[];
  my_restatement?: string;
  error?: string;
}

/** the compact terms.json used by ⌘K (one entry per glossary term) */
export interface TermLite {
  slug: string;
  term: string;
  en?: string;
  definition?: string;
  category?: string;
}

export interface ParsedHolding {
  symbol: string;
  name?: string | null;
  quantity?: number | null;
  value_usd?: number | null;
  market?: string | null;
  dust?: boolean;
}

export interface ExchangeKeyInfo {
  id: number;
  exchange: string;
  label: string;
  key_masked: string;
  manual_usd: number;
}

export interface ExchangeSnapshot {
  total_usdt: number;
  wallet_usdt?: number;
  tradfi_usdt?: number;
  manual_usd?: number;
  by_account: Record<string, number>;
  spot: { coin: string; amount: number; usd: number }[];
  finance?: { coin: string; product: string; amount: number; usd: number }[];
  futures: { contract: string; size: number; value: number; upnl: number }[];
}

export interface ReportState {
  status: "idle" | "running" | "done" | "error" | string;
  report?: string;
  generated_at?: string | null;
  can_push?: boolean;
  error?: string;
}

export interface AnalysisItem {
  id: number;
  ticker: string;
  company_name?: string;
  market?: string;
  status: "running" | "done" | "error" | string;
  created_at?: string;
}

export interface AnalysisDetail extends AnalysisItem {
  report?: string;
  generated_at?: string | null;
  error?: string;
}

/** ---- company-analysis dashboard (real data from /api/companies/*) ---- */
type Num = number | null;

export interface CompanySnapshot {
  ticker: string;
  market: string;
  as_of?: string;
  profile: {
    name?: string; sector?: string | null; industry?: string | null;
    exchange?: string | null; currency?: string | null; country?: string | null;
    employees?: number | null; website?: string | null; summary?: string | null;
  };
  quote: {
    price?: Num; change_pct?: Num; market_cap?: Num; currency?: string | null;
    fifty_two_week_high?: Num; fifty_two_week_low?: Num;
  };
  metrics: {
    pe?: Num; forward_pe?: Num; pb?: Num; ps?: Num; dividend_yield?: Num;
    roe?: Num; gross_margin?: Num; operating_margin?: Num; net_margin?: Num;
    debt_to_equity?: Num; debt_to_assets?: Num; current_ratio?: Num;
    revenue_growth?: Num; earnings_growth?: Num; fcf?: Num;
  };
  financials: {
    years?: string[]; revenue?: Num[]; net_income?: Num[]; eps?: Num[]; fcf?: Num[];
    gross_margin?: Num[]; net_margin?: Num[];
  };
  price_history: { dates?: string[]; ohlc?: number[][]; close?: number[] };
  radar: { indicators?: { name: string; max: number }[]; values?: Num[]; notes?: Record<string, string> };
  valuation_history: {
    pe_percentile?: Num; pb_percentile?: Num; price_percentile?: Num;
    span?: string; method?: string;
  };
  valuation_signals?: {
    tools?: { key: string; name: string; verdict: string; detail: string }[];
    cheap_count?: number;
    scored_count?: number;
    deep_research?: boolean;
    reverse_dcf?: {
      implied_growth?: Num; hist_rev_cagr?: Num; hist_eps_cagr?: Num; owner_earnings?: Num;
      assumptions?: { discount_rate: number; terminal_growth: number; years: number };
    };
    ev_ebit?: Num; owner_earnings_yield?: Num; ten_year_yield?: Num; net_debt?: Num;
  };
  quality_signals?: {
    cash_conversion?: { cum_fcf_ni?: Num; latest_fcf_ni?: Num; years?: number; verdict?: string } | null;
    accruals?: { rev_cagr?: Num; recv_cagr?: Num; inv_cagr?: Num; recv_flag?: boolean; inv_flag?: boolean } | null;
    incremental_roic?: { incremental?: Num; avg_roic?: Num; verdict?: string } | null;
    goodwill_ratio?: Num;
    payout_ratio?: Num;
    fixed_charge_coverage?: Num;
    red_flags?: { name: string; hit: boolean; detail: string }[];
    flag_count?: number;
  };
  history_position?: {
    span?: string;
    metrics?: { name: string; unit: string; current: number; min: number; max: number; avg: number; position: number; state: string }[];
    note?: string;
  };
  macro_signal?: {
    env?: {
      ten_year?: Num; ten_year_1y_ago?: Num; short_rate?: Num; curve_slope?: Num;
      curve_state?: string; rate_trend?: string; lpr_1y?: Num; m2_growth?: Num;
    };
    sensitivity?: { score?: string; drivers?: string[] };
    note?: string;
  };
  warnings?: string[];
  _schema?: number;
  _cached?: boolean;
  _age_s?: number;
}

export interface CompanyNewsItem {
  title?: string; link?: string | null; publisher?: string; time?: string | null;
  type?: "news" | "filing" | string; form?: string;
}

export interface CompanyNews {
  ticker: string; market: string;
  news: CompanyNewsItem[]; filings: CompanyNewsItem[];
  warnings?: string[];
}

export interface CompanyPeerRow {
  ticker?: string; name?: string; market_cap?: Num; pe?: Num; pb?: Num; ps?: Num;
  ev_ebitda?: Num; roe?: Num; gross_margin?: Num; net_margin?: Num; revenue_growth?: Num;
  is_self?: boolean;
}

export interface CompanyPeers {
  ticker: string; market: string; industry?: string | null;
  rows: CompanyPeerRow[];
  percentiles: Record<string, Num>;
  ev_ebit_verdict?: string;
  mispricing?: string | null;
  warnings?: string[];
}

export interface ChatTurn { question?: string; reply?: string }
export interface AsyncJob { status: "running" | "done" | "error" | string; reply?: string; error?: string }
export interface CuratedTerm { term: string; term_en?: string; definition?: string; slug: string }
export interface ExplainResp { id: number; curated?: CuratedTerm | null; error?: string }

export interface SignalCard {
  tldr: string;
  non_consensus: string;
  new_angle: string;
  pillar: string;
  caution: string;
  worth_relisten: { yes: boolean; timestamps: string[] };
}

export interface Signal {
  external_id: string;
  source: string;
  show_title?: string | null;
  image_url?: string | null;
  title: string;
  url: string;
  published_at?: string | null;
  card: SignalCard;
}

export interface SignalDetail extends Signal {
  transcript?: string | null;
}

export interface CycleLens {
  key: string;
  title: string;
  score: number | null;
  label: string;
  detail: string;
}

export interface MarketCycle {
  _schema?: number;
  market: string;
  composite: {
    score: number | null;
    level: number;
    position: string;
    tailwind: string;
    sahm_breaker: boolean;
    lenses_used: string[];
    lenses_missing: string[];
  };
  lenses: CycleLens[];
  asset_tilt: Record<string, string>;
  cape_flag: { on: boolean; note: string };
  recession_prob: number | null;
  fred_enabled: boolean;
  warnings: string[];
}

export interface SectorHeat {
  ticker: string;
  name: string;
  quadrant: string;
  heat: number | null;
  rs_6m: number | null;
  rs_3m: number | null;
}

export interface MarketBoard {
  _schema?: number;
  market: string;
  temperature: { valuation?: string; breadth?: string; concentrated?: boolean | null; hot?: boolean; note?: string };
  valuation: {
    percentile: number | null; level: number | null; label: string; note: string;
    pe?: { value: number; percentile: number | null } | null;
    cape?: { value: number; percentile: number | null } | null;
  };
  concentration: {
    top_n_weight: number | null; herfindahl: number | null; rsp_spy_percentile: number | null;
    top_n: number; concentrated: boolean | null; label: string; detail: string;
  };
  breadth: { pct_above_200: number | null; pct_above_50: number | null; level: number | null; label: string; healthy: boolean | null; n?: number | null };
  sectors: SectorHeat[];
  crowding_note?: string;
  warnings: string[];
}

export interface MarketRates {
  _schema?: number;
  market: string;
  policy_rates: { name: string; value: string; detail?: string; asof?: string | null }[];
  future_path: {
    market_implied?: { dgs2: number; gap_bps: number; direction: string; note: string } | null;
    dot_plot?: { points: [number, number][]; direction: string; note: string } | null;
    comparison?: string;
    t10yff?: number | null;
  };
  macro: { name: string; value: string; trend?: string | null; asof?: string | null }[];
  fred_enabled?: boolean;
  warnings: string[];
}

export interface MarketSentiment {
  _schema?: number;
  market: string;
  fear_greed: { score: number | null; level: number | null; label: string; contrarian?: string; rating?: string | null; subs?: { name: string; rating: string }[] };
  vix_term: { ivts?: number; vix?: number; vix3m?: number; label: string; detail?: string };
  composite: { label: string; note?: string };
  warnings: string[];
}

export interface MarketReview {
  status: "none" | "running" | "done" | "error";
  report?: string;
  generated_at?: number;
  error?: string;
  _age_s?: number;
}

export interface SectorLeaders {
  _schema?: number;
  market: string;
  sectors: { etf: string; name: string; leaders: { ticker: string; name: string; weight: number }[] }[];
  note?: string;
  warnings: string[];
}

export interface MarketCN {
  _schema?: number;
  market: string;
  valuation: { index?: string; pe?: number; percentile?: number | null; label?: string; level?: number | null; note?: string };
  rates: {
    policy_rates?: { name: string; value: string }[];
    ten_year?: number; curve_slope?: number;
    m2_yoy?: number | null; m1_yoy?: number | null; m1_m2_gap?: number | null; pmi?: number | null; note?: string;
  };
  sentiment: { margin_balance_yi?: number; trend_20d_pct?: number | null; as_of?: string; note?: string };
  note?: string;
  warnings: string[];
}

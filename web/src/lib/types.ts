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

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

export interface ChatTurn { question?: string; reply?: string }
export interface AsyncJob { status: "running" | "done" | "error" | string; reply?: string; error?: string }
export interface CuratedTerm { term: string; term_en?: string; definition?: string; slug: string }
export interface ExplainResp { id: number; curated?: CuratedTerm | null; error?: string }

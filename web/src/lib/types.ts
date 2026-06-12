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
  est_minutes: number;
  why?: string;
  read?: boolean;
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

import { logApi } from './client';

export interface DispatchDecisionListItem {
  decision_id: string;
  order_id: string;
  timestamp: string;
  assigned_to: string;
  carrier_type: string;
  assignment_source: string;
  algorithm_version: string;
  winner_score: number;
  reason_summary: string;
}

export interface DecisionListResponse {
  items: DispatchDecisionListItem[];
}

export interface FactorDetail {
  name: string;
  raw_value: number | string | null;
  normalized_value: number;
  weight: number;
  explanation: string;
}

export type DecisionContextSnapshot = Record<string, unknown>;

export interface DecisionDetailResponse {
  decision_id: string;
  order_id: string;
  timestamp: string;
  assigned_to: string;
  carrier_type: string;
  assignment_source: string;
  algorithm_version: string;
  scores: Record<string, number>;
  winner_score: number;
  reason_summary: string;
  factors: FactorDetail[];
  context_snapshot: DecisionContextSnapshot;
  override_info: unknown;
}

export async function listDecisions(params?: { assignment_source?: string; limit?: number; offset?: number }) {
  const res = await logApi.get<DecisionListResponse>('/decisions', { params });
  return res.data;
}

export async function getDecision(decisionId: string) {
  const res = await logApi.get<DecisionDetailResponse>(`/decisions/${decisionId}`);
  return res.data;
}

export interface OverrideRateResponse {
  override_rate: number;
  overrides: number;
  total: number;
  alert: boolean;
}

export async function getOverrideRate() {
  const res = await logApi.get<OverrideRateResponse>('/decisions/analytics/override_rate');
  return res.data;
}


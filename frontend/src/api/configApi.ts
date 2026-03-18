import { configApi } from './client';

export interface AlgorithmConfig {
  config_id: string;
  version: string;
  name: string;
  description: string;
  weights: Record<string, number>;
  staff_priority_bonus: number;
  sla_fallback_threshold: number;
  is_active: boolean;
  kitchen_ids: string[];
  created_by: string;
  approved_by?: string | null;
  created_at?: string;
}

export interface ConfigListResponse {
  items: AlgorithmConfig[];
}

export interface CreateConfigBody {
  version: string;
  name: string;
  description?: string;
  created_by: string;
}

export async function listConfigs(activeOnly?: boolean) {
  const res = await configApi.get<ConfigListResponse>('/configs', {
    params: activeOnly ? { active_only: true } : undefined,
  });
  return res.data;
}

export async function updateConfig(configId: string, body: { is_active?: boolean }) {
  const res = await configApi.patch<AlgorithmConfig>(`/configs/${configId}`, body);
  return res.data;
}

export async function createConfig(body: CreateConfigBody) {
  const payload = {
    version: body.version,
    name: body.name,
    description: body.description ?? '',
    // Остальные поля (weights, staff_priority_bonus, sla_fallback_threshold, kitchen_ids)
    // будут заполнены дефолтами на бэкенде.
    created_by: body.created_by,
  };
  const res = await configApi.post<AlgorithmConfig>('/configs', payload);
  return res.data;
}

export async function assignConfigToKitchen(configId: string, kitchenId: string) {
  const res = await configApi.post<{ kitchen_id: string; config_id: string }>('/configs/assign', {
    config_id: configId,
    kitchen_id: kitchenId,
  });
  return res.data;
}


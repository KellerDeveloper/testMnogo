import { courierApi } from './client';

export type CourierStatus = 'idle' | 'delivering' | 'returning' | 'offline';

export interface Courier {
  courier_id: string;
  kitchen_id: string;
  name: string;
  status: CourierStatus;
  current_location?: { lat: number; lon: number } | null;
  current_orders: string[];
  max_batch_size: number;
  orders_delivered_today: number;
  total_delivery_time_today: number;
  geo_trust_score: number;
  arrival_qr_token?: string | null;
  arrival_qr_expires_at?: string | null;
}

export interface AvailableCouriersResponse {
  items: Courier[];
}

export async function fetchAvailableCouriers(kitchenId: string) {
  const res = await courierApi.get<AvailableCouriersResponse>(`/couriers/available/${kitchenId}`);
  return res.data;
}

/** All couriers for a kitchen (any status). Use to show offline couriers and start shift from UI. */
export async function fetchCouriersByKitchen(kitchenId: string) {
  const res = await courierApi.get<AvailableCouriersResponse>('/couriers', {
    params: { kitchen_id: kitchenId },
  });
  return res.data;
}

export interface CreateCourierBody {
  kitchen_id: string;
  name: string;
  max_batch_size?: number;
}

export async function createCourier(body: CreateCourierBody) {
  const res = await courierApi.post<Courier & { courier_id: string }>('/couriers', {
    ...body,
    max_batch_size: body.max_batch_size ?? 3,
  });
  return res.data;
}

export interface CourierStatsSummary {
  courier_id: string;
  name?: string;
  orders_delivered_today: number;
  total_delivery_time_today_minutes: number;
  kitchen_avg_orders_today: number;
  rank_by_orders: number;
  total_couriers_on_kitchen: number;
}

export async function fetchCourierStatsSummary(courierId: string) {
  const res = await courierApi.get<CourierStatsSummary>(`/couriers/${courierId}/stats_summary`);
  return res.data;
}

export async function sendCourierFeedback(courierId: string, body: { reason: string; comment?: string }) {
  await courierApi.post(`/couriers/${courierId}/feedback`, body);
}

export async function fetchCourier(courierId: string) {
  const res = await courierApi.get<Courier>(`/couriers/${courierId}`);
  return res.data;
}

export async function startShift(courierId: string) {
  const res = await courierApi.post<Courier>(`/couriers/${courierId}/shift/start`);
  return res.data;
}

export async function endShift(courierId: string) {
  const res = await courierApi.post<Courier>(`/couriers/${courierId}/shift/end`);
  return res.data;
}

export async function updateCourierStatus(courierId: string, status: CourierStatus) {
  const res = await courierApi.patch<Courier>(`/couriers/${courierId}/status`, { status });
  return res.data;
}

export async function updateCourierLocation(courierId: string, lat: number, lon: number) {
  const res = await courierApi.patch<Courier>(`/couriers/${courierId}/location`, { lat, lon });
  return res.data;
}

export async function recordDelivery(courierId: string, orderId: string, deliveryTimeMinutes: number = 0) {
  const res = await courierApi.post<Courier>(`/couriers/${courierId}/delivered`, null, {
    params: { order_id: orderId, delivery_time_minutes: deliveryTimeMinutes },
  });
  return res.data;
}

export async function requestArrivalQR(courierId: string) {
  const res = await courierApi.post<{ token: string; expires_at: string | null }>(`/couriers/${courierId}/arrival_qr`);
  return res.data;
}

export async function confirmArrival(courierId: string, token: string) {
  const res = await courierApi.post<Courier>(`/couriers/${courierId}/arrival_confirm`, { token });
  return res.data;
}


import { orderApi } from './client';

export type OrderStatus = 'new' | 'pending' | 'assigned' | 'picked_up' | 'delivered' | 'cancelled';

export interface Order {
  order_id: string;
  kitchen_id: string;
  customer_location: { lat: number; lon: number };
  promised_delivery_time: string;
  preparation_ready_time?: string | null;
  status: OrderStatus;
  assigned_courier_id?: string | null;
  assigned_carrier_type?: 'staff' | '3pl' | null;
  assignment_source?: 'dispatcher_auto' | 'manual_override' | null;
  created_at: string;
}

export interface OrderListResponse {
  items: Order[];
  total: number;
}

export async function fetchOrders(params?: { kitchen_id?: string; status?: string }) {
  const res = await orderApi.get<OrderListResponse>('/orders', { params });
  return res.data;
}

export async function fetchOrder(orderId: string) {
  const res = await orderApi.get<Order>(`/orders/${orderId}`);
  return res.data;
}

export async function markReadyForDispatch(orderId: string) {
  const res = await orderApi.post<Order>(`/orders/${orderId}/ready_for_dispatch`);
  return res.data;
}

export async function manualAssign(orderId: string, body: { operator_id: string; courier_id: string; override_reason?: string | null }) {
  const res = await orderApi.post<Order>(`/orders/${orderId}/manual_assign`, body);
  return res.data;
}

export interface CreateOrderBody {
  kitchen_id: string;
  customer_location: { lat: number; lon: number };
  promised_delivery_time: string; // ISO
  preparation_time_estimate_minutes?: number | null;
}

export async function createOrder(body: CreateOrderBody) {
  const res = await orderApi.post<Order & { order_id: string }>('/orders', body, { validateStatus: () => true });
  if (res.status >= 400) throw new Error(res.data?.detail ?? 'Failed to create order');
  return res.data;
}

export async function updateOrderStatus(
  orderId: string,
  body: { status: 'picked_up' | 'delivered' | 'cancelled'; courier_id?: string; reason?: string }
) {
  const res = await orderApi.post<Order>(`/orders/${orderId}/status`, body);
  return res.data;
}


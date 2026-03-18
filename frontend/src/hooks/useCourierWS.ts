import { useEffect, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';

const courierBase = import.meta.env.VITE_COURIER_API ?? (import.meta.env.DEV ? '/api/courier' : 'http://localhost:8001');

function getCourierWSUrl(): string {
  if (courierBase.startsWith('/')) {
    const protocol = typeof window !== 'undefined' && window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${protocol}//${typeof window !== 'undefined' ? window.location.host : 'localhost:3000'}${courierBase}/ws`;
  }
  return courierBase.replace(/^http/, 'ws') + '/ws';
}

/**
 * Подписка на обновления курьеров по WebSocket.
 * @param kitchenId — подписка на всех курьеров кухни (для страницы кухни)
 * @param courierId — подписка на одного курьера (для приложения курьера)
 * При событии courier_changed — invalidate соответствующих запросов.
 * @returns connected — true, когда WebSocket открыт и подписка отправлена
 */
export function useCourierWS(options: { kitchenId?: string; courierId?: string }): { connected: boolean } {
  const { kitchenId, courierId } = options;
  const queryClient = useQueryClient();
  const wsRef = useRef<WebSocket | null>(null);
  const cancelledRef = useRef(false);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    const key = kitchenId ?? courierId;
    if (!key) {
      setConnected(false);
      return;
    }
    cancelledRef.current = false;
    setConnected(false);

    const wsUrl = getCourierWSUrl();
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      if (cancelledRef.current) {
        ws.close();
        return;
      }
      if (kitchenId) {
        ws.send(JSON.stringify({ action: 'subscribe', kitchen_id: kitchenId }));
      } else if (courierId) {
        ws.send(JSON.stringify({ action: 'subscribe', courier_id: courierId }));
      }
      setConnected(true);
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type !== 'courier_changed') return;
        if (kitchenId && msg.kitchen_id === kitchenId) {
          queryClient.invalidateQueries({ queryKey: ['couriersByKitchen', kitchenId] });
          queryClient.invalidateQueries({ queryKey: ['availableCouriers', kitchenId] });
        }
        if (courierId && msg.courier_id === courierId) {
          queryClient.invalidateQueries({ queryKey: ['courier', courierId] });
          queryClient.invalidateQueries({ queryKey: ['ordersForCourier'] });
          queryClient.invalidateQueries({ queryKey: ['courierStats', courierId] });
        }
      } catch {
        // ignore
      }
    };

    ws.onerror = () => setConnected(false);
    ws.onclose = () => setConnected(false);

    return () => {
      cancelledRef.current = true;
      wsRef.current = null;
      setConnected(false);
      if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CLOSING) {
        ws.close();
      }
    };
  }, [kitchenId, courierId, queryClient]);

  return { connected };
}

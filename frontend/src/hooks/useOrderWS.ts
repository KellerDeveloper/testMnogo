import { useEffect, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';

const orderBase = import.meta.env.VITE_ORDER_API ?? (import.meta.env.DEV ? '/api/order' : 'http://localhost:8000');

function getOrderWSUrl(): string {
  if (orderBase.startsWith('/')) {
    const protocol = typeof window !== 'undefined' && window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${protocol}//${typeof window !== 'undefined' ? window.location.host : 'localhost:3000'}${orderBase}/ws`;
  }
  return orderBase.replace(/^http/, 'ws') + '/ws';
}

/**
 * Подписка на обновления заказов кухни по WebSocket. При событии orders_changed — invalidate запросов заказов.
 * @returns connected — true, когда WebSocket открыт и подписка отправлена
 */
export function useOrderWS(kitchenId: string | undefined): { connected: boolean } {
  const queryClient = useQueryClient();
  const wsRef = useRef<WebSocket | null>(null);
  const cancelledRef = useRef(false);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    if (!kitchenId) {
      setConnected(false);
      return;
    }
    cancelledRef.current = false;
    setConnected(false);

    const wsUrl = getOrderWSUrl();
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      if (cancelledRef.current) {
        ws.close();
        return;
      }
      ws.send(JSON.stringify({ action: 'subscribe', kitchen_id: kitchenId }));
      setConnected(true);
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === 'orders_changed' && msg.kitchen_id === kitchenId) {
          queryClient.invalidateQueries({ queryKey: ['orders'] });
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
      // Если ещё CONNECTING — не закрываем здесь, чтобы не вызывать "closed before connection is established";
      // onopen проверит cancelledRef и закроет сокет.
    };
  }, [kitchenId, queryClient]);

  return { connected };
}

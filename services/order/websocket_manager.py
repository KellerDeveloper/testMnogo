import json
from collections import defaultdict

from fastapi import WebSocket


class OrderWSManager:
    """Подписки по kitchen_id. При изменении заказов кухни — рассылка всем подписчикам."""

    def __init__(self):
        self._by_kitchen: dict[str, set[WebSocket]] = defaultdict(set)

    async def subscribe(self, websocket: WebSocket, kitchen_id: str) -> None:
        self._by_kitchen[kitchen_id].add(websocket)

    def unsubscribe(self, websocket: WebSocket, kitchen_id: str) -> None:
        self._by_kitchen[kitchen_id].discard(websocket)
        if not self._by_kitchen[kitchen_id]:
            del self._by_kitchen[kitchen_id]

    async def broadcast_orders_changed(self, kitchen_id: str) -> None:
        payload = json.dumps({"type": "orders_changed", "kitchen_id": str(kitchen_id)})
        dead = set()
        for ws in self._by_kitchen.get(str(kitchen_id), []):
            try:
                await ws.send_text(payload)
            except Exception:
                dead.add(ws)
        for ws in dead:
            self._by_kitchen[str(kitchen_id)].discard(ws)


order_ws_manager = OrderWSManager()

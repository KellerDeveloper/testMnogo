import json
from collections import defaultdict

from fastapi import WebSocket


class CourierWSManager:
    """Подписки по courier_id и по kitchen_id. При изменении курьера — рассылка подписчикам."""

    def __init__(self):
        self._by_courier: dict[str, set[WebSocket]] = defaultdict(set)
        self._by_kitchen: dict[str, set[WebSocket]] = defaultdict(set)

    async def subscribe_courier(self, websocket: WebSocket, courier_id: str) -> None:
        self._by_courier[courier_id].add(websocket)

    async def subscribe_kitchen(self, websocket: WebSocket, kitchen_id: str) -> None:
        self._by_kitchen[kitchen_id].add(websocket)

    def unsubscribe_courier(self, websocket: WebSocket, courier_id: str) -> None:
        self._by_courier[courier_id].discard(websocket)
        if not self._by_courier[courier_id]:
            del self._by_courier[courier_id]

    def unsubscribe_kitchen(self, websocket: WebSocket, kitchen_id: str) -> None:
        self._by_kitchen[kitchen_id].discard(websocket)
        if not self._by_kitchen[kitchen_id]:
            del self._by_kitchen[kitchen_id]

    async def broadcast_courier_changed(self, courier_id: str, kitchen_id: str) -> None:
        payload = json.dumps({"type": "courier_changed", "courier_id": courier_id, "kitchen_id": str(kitchen_id)})
        kid = str(kitchen_id)
        for ws in list(self._by_courier.get(courier_id, [])):
            try:
                await ws.send_text(payload)
            except Exception:
                self._by_courier[courier_id].discard(ws)
        for ws in list(self._by_kitchen.get(kid, [])):
            try:
                await ws.send_text(payload)
            except Exception:
                self._by_kitchen[kid].discard(ws)


courier_ws_manager = CourierWSManager()

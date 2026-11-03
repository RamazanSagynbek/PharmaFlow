"""WebSocket: live simulation snapshots for the SCADA dashboard."""
import asyncio
import contextlib

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


class ConnectionManager:
    def __init__(self) -> None:
        self.clients: set[WebSocket] = set()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.clients.add(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self.clients.discard(ws)

    async def broadcast(self, message: dict) -> None:
        clients = list(self.clients)
        if not clients:
            return
        results = await asyncio.gather(
            *(ws.send_json(message) for ws in clients), return_exceptions=True
        )
        for ws, result in zip(clients, results, strict=True):
            if isinstance(result, Exception):
                self.disconnect(ws)


manager = ConnectionManager()


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    runner = ws.app.state.runner
    await ws.send_json({"type": "hello", "snapshot": runner.sim.snapshot(), "running": runner.running})
    with contextlib.suppress(WebSocketDisconnect):
        while True:
            await ws.receive_text()  # keep-alive; the server pushes ticks
    manager.disconnect(ws)

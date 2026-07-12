import json
import time
from typing import Dict, List, Set
from fastapi import WebSocket
from uuid import UUID


class ConnectionManager:
    def __init__(self):
        self._connections: Dict[str, List[WebSocket]] = {}
        self._global_listeners: List[WebSocket] = []

    async def connect(self, websocket: WebSocket, canvas_id: str = None):
        await websocket.accept()
        if canvas_id:
            if canvas_id not in self._connections:
                self._connections[canvas_id] = []
            self._connections[canvas_id].append(websocket)
        else:
            self._global_listeners.append(websocket)

    def disconnect(self, websocket: WebSocket, canvas_id: str = None):
        # 不依赖 canvas_id 参数：先从全局监听器移除，再遍历所有 canvas 连接列表移除
        try:
            self._global_listeners.remove(websocket)
        except ValueError:
            pass
        empty = []
        for cid, conns in self._connections.items():
            try:
                conns.remove(websocket)
            except ValueError:
                pass
            if not conns:
                empty.append(cid)
        for cid in empty:
            del self._connections[cid]

    async def _close_and_remove(self, ws: WebSocket):
        """关闭失活连接并从所有连接列表中移除。"""
        try:
            await ws.close()
        except Exception:
            pass
        try:
            self._global_listeners.remove(ws)
        except ValueError:
            pass
        empty = []
        for cid, conns in self._connections.items():
            try:
                conns.remove(ws)
            except ValueError:
                pass
            if not conns:
                empty.append(cid)
        for cid in empty:
            del self._connections[cid]

    async def send_to_canvas(self, canvas_id: str, message: dict):
        data = json.dumps(message, ensure_ascii=False, default=str)
        targets = []
        if canvas_id in self._connections:
            targets.extend(self._connections[canvas_id])
        targets.extend(self._global_listeners)
        dead = []
        for ws in targets:
            try:
                await ws.send_text(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            await self._close_and_remove(ws)

    async def broadcast_heartbeat(self):
        """向所有连接发送心跳，并清理失活连接。"""
        message = {"type": "heartbeat", "ts": time.time()}
        data = json.dumps(message, ensure_ascii=False, default=str)
        dead = []
        for conns in self._connections.values():
            for ws in conns:
                try:
                    await ws.send_text(data)
                except Exception:
                    dead.append(ws)
        for ws in self._global_listeners[:]:
            try:
                await ws.send_text(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            await self._close_and_remove(ws)

    def _sanitize_task_result(self, result):
        if not isinstance(result, dict):
            return result
        cleaned = dict(result)
        if "raw_response" in cleaned:
            cleaned["raw_response"] = "<trimmed>"
        return cleaned

    async def send_task_update(self, task):
        message = {
            "type": "task_update",
            "task_id": task.id,
            "node_id": task.node_id,
            "canvas_id": task.canvas_id,
            "status": task.status.value,
            "progress": task.progress,
            "result": self._sanitize_task_result(task.result),
            "error": task.error,
            "retry_count": task.retry_count,
        }
        await self.send_to_canvas(task.canvas_id, message)

    def get_connection_count(self) -> int:
        count = len(self._global_listeners)
        for conns in self._connections.values():
            count += len(conns)
        return count


ws_manager = ConnectionManager()
# 向后兼容别名
manager = ws_manager

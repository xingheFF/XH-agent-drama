import json
import time
from typing import Dict, List, Optional
from fastapi import WebSocket
from uuid import UUID


# 协作者光标/标识颜色池
_COLLAB_COLORS = [
    "#ef4444", "#f97316", "#f59e0b", "#84cc16", "#10b981",
    "#06b6d4", "#3b82f6", "#6366f1", "#8b5cf6", "#d946ef",
    "#f43f5e", "#14b8a6", "#0ea5e9", "#a855f7",
]


class ConnectionManager:
    def __init__(self):
        self._connections: Dict[str, List[WebSocket]] = {}
        self._global_listeners: List[WebSocket] = []
        # 每个 WebSocket 的元数据：user_id / username / color / canvas_id
        self._meta: Dict[int, dict] = {}
        self._color_index = 0

    def _next_color(self) -> str:
        color = _COLLAB_COLORS[self._color_index % len(_COLLAB_COLORS)]
        self._color_index += 1
        return color

    async def connect(
        self,
        websocket: WebSocket,
        canvas_id: str = None,
        user_id: str = None,
        username: str = None,
    ) -> dict:
        await websocket.accept()
        meta = {
            "user_id": str(user_id) if user_id else None,
            "username": username or "未知用户",
            "color": self._next_color(),
            "canvas_id": canvas_id,
        }
        self._meta[id(websocket)] = meta
        if canvas_id:
            if canvas_id not in self._connections:
                self._connections[canvas_id] = []
            self._connections[canvas_id].append(websocket)
        else:
            self._global_listeners.append(websocket)
        return meta

    def get_meta(self, websocket: WebSocket) -> Optional[dict]:
        return self._meta.get(id(websocket))

    def disconnect(self, websocket: WebSocket, canvas_id: str = None) -> Optional[dict]:
        meta = self._meta.pop(id(websocket), None)
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
        return meta

    async def _close_and_remove(self, ws: WebSocket):
        """关闭失活连接并从所有连接列表中移除。"""
        try:
            await ws.close()
        except Exception:
            pass
        self._meta.pop(id(ws), None)
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

    async def send_to_canvas(
        self,
        canvas_id: str,
        message: dict,
        exclude_ws: WebSocket = None,
        only_ws: WebSocket = None,
    ):
        """向指定画布的所有连接广播消息。

        Args:
            only_ws: 若指定，则只发送给该连接（用于单播欢迎消息）。
            exclude_ws: 若指定，则排除该连接（用于排除发送者）。
        """
        data = json.dumps(message, ensure_ascii=False, default=str)
        targets = []
        if only_ws:
            targets.append(only_ws)
        else:
            if canvas_id in self._connections:
                targets.extend(self._connections[canvas_id])
            targets.extend(self._global_listeners)
        dead = []
        for ws in targets:
            if exclude_ws and ws is exclude_ws:
                continue
            try:
                await ws.send_text(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            await self._close_and_remove(ws)

    async def broadcast_to_canvas(
        self,
        canvas_id: str,
        message: dict,
        exclude_ws: WebSocket = None,
    ):
        """协作广播：向画布内所有人发送（默认不排除）。"""
        await self.send_to_canvas(canvas_id, message, exclude_ws=exclude_ws)

    def get_canvas_users(self, canvas_id: str) -> List[dict]:
        """获取当前画布在线用户列表。"""
        users = []
        seen = set()
        for ws in self._connections.get(canvas_id, []):
            meta = self._meta.get(id(ws))
            if not meta:
                continue
            uid = meta.get("user_id")
            if not uid or uid in seen:
                continue
            seen.add(uid)
            users.append({
                "user_id": uid,
                "username": meta.get("username"),
                "color": meta.get("color"),
            })
        return users

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

    async def handle_canvas_message(
        self,
        websocket: WebSocket,
        canvas_id: str,
        msg: dict,
    ):
        """处理前端发来的协作消息，并广播给同画布其他用户。"""
        msg_type = msg.get("type")
        meta = self._meta.get(id(websocket), {})
        user_id = meta.get("user_id")
        username = meta.get("username")
        color = meta.get("color")

        if msg_type == "cursor_move":
            # 光标只广播给其他人，发送者不需要看到自己的光标
            await self.broadcast_to_canvas(canvas_id, {
                "type": "cursor_move",
                "canvas_id": canvas_id,
                "user_id": user_id,
                "username": username,
                "color": color,
                "x": msg.get("x"),
                "y": msg.get("y"),
            }, exclude_ws=websocket)
            return

        base = {
            "canvas_id": canvas_id,
            "by_user_id": user_id,
            "by_username": username,
        }

        if msg_type == "node_add":
            await self.broadcast_to_canvas(canvas_id, {
                **base,
                "type": "node_add",
                "node": msg.get("node"),
            })
        elif msg_type == "node_update":
            await self.broadcast_to_canvas(canvas_id, {
                **base,
                "type": "node_update",
                "node_id": msg.get("node_id"),
                "data": msg.get("data"),
            })
        elif msg_type == "node_delete":
            await self.broadcast_to_canvas(canvas_id, {
                **base,
                "type": "node_delete",
                "node_id": msg.get("node_id"),
            })
        elif msg_type == "edge_add":
            await self.broadcast_to_canvas(canvas_id, {
                **base,
                "type": "edge_add",
                "edge": msg.get("edge"),
            })
        elif msg_type == "edge_update":
            await self.broadcast_to_canvas(canvas_id, {
                **base,
                "type": "edge_update",
                "edge_id": msg.get("edge_id"),
                "data": msg.get("data"),
            })
        elif msg_type == "edge_delete":
            await self.broadcast_to_canvas(canvas_id, {
                **base,
                "type": "edge_delete",
                "edge_id": msg.get("edge_id"),
            })
        elif msg_type == "node_positions":
            await self.broadcast_to_canvas(canvas_id, {
                **base,
                "type": "node_positions",
                "positions": msg.get("positions"),
            })
        # ping/pong 已在底层处理，非协作消息忽略即可

    def get_connection_count(self) -> int:
        count = len(self._global_listeners)
        for conns in self._connections.values():
            count += len(conns)
        return count


ws_manager = ConnectionManager()
# 向后兼容别名
manager = ws_manager

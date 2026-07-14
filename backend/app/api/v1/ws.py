import json
import logging
from uuid import UUID
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.ws import ws_manager
from app.core.permissions import can_access_canvas
from app.services.auth_service import decode_access_token, get_user_by_id
from app.crud import canvas as crud_canvas

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])


async def _verify_ws_token(websocket: WebSocket) -> bool:
    """从 query 参数或子协议中提取 JWT token 并验证。

    支持两种传参方式：
    1. query 参数 ?token=xxx（最通用）
    2. Sec-WebSocket-Protocol 子协议（前端 new WebSocket(url, [token])）
    """
    token = websocket.query_params.get("token")
    if not token:
        # 尝试从子协议中获取
        subprotocols = websocket.headers.get("sec-websocket-protocol", "")
        if subprotocols:
            token = subprotocols.split(",")[0].strip()
    if not token:
        await websocket.close(code=4001, reason="未提供认证 Token")
        return False
    payload = decode_access_token(token)
    if not payload or not payload.get("sub"):
        await websocket.close(code=4001, reason="Token 无效或已过期")
        return False
    return True


def _extract_token(websocket: WebSocket) -> str:
    token = websocket.query_params.get("token", "")
    if not token:
        subprotocols = websocket.headers.get("sec-websocket-protocol", "")
        if subprotocols:
            token = subprotocols.split(",")[0].strip()
    return token


@router.websocket("/ws/canvas/{canvas_id}")
async def websocket_canvas(
    websocket: WebSocket,
    canvas_id: str,
    db: Session = Depends(get_db),
):
    if not await _verify_ws_token(websocket):
        return

    token = _extract_token(websocket)
    payload = decode_access_token(token)
    user_id = payload.get("sub")

    # 校验画布访问权限
    try:
        canvas_uuid = UUID(canvas_id)
    except ValueError:
        await websocket.close(code=4004, reason="画布ID格式错误")
        return

    canvas = crud_canvas.get_canvas(db, canvas_uuid)
    if not canvas or not can_access_canvas(db, user_id, canvas):
        await websocket.close(code=4003, reason="无权访问该画布")
        return

    # 查询用户名
    try:
        user = get_user_by_id(db, UUID(user_id))
        username = user.name or user.email or user_id[:8]
    except Exception:
        username = user_id[:8]

    meta = await ws_manager.connect(
        websocket,
        canvas_id=canvas_id,
        user_id=user_id,
        username=username,
    )

    # 通知其他人有新用户加入
    await ws_manager.broadcast_to_canvas(
        canvas_id,
        {
            "type": "user_joined",
            "canvas_id": canvas_id,
            "user_id": user_id,
            "username": username,
            "color": meta.get("color"),
        },
        exclude_ws=websocket,
    )

    # 向新连接者发送当前在线列表
    await ws_manager.send_to_canvas(
        canvas_id,
        {
            "type": "presence",
            "canvas_id": canvas_id,
            "users": ws_manager.get_canvas_users(canvas_id),
        },
        only_ws=websocket,
    )

    try:
        await ws_manager.send_to_canvas(
            canvas_id,
            {
                "type": "connected",
                "canvas_id": canvas_id,
                "message": "WebSocket连接成功",
            },
            only_ws=websocket,
        )
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
            except json.JSONDecodeError:
                continue
            # 忽略纯心跳
            if msg.get("type") in ("ping", "pong"):
                continue
            await ws_manager.handle_canvas_message(websocket, canvas_id, msg)
    except WebSocketDisconnect:
        left_meta = ws_manager.disconnect(websocket, canvas_id=canvas_id)
        await ws_manager.broadcast_to_canvas(
            canvas_id,
            {
                "type": "user_left",
                "canvas_id": canvas_id,
                "user_id": left_meta.get("user_id") if left_meta else None,
            },
            exclude_ws=websocket,
        )


@router.websocket("/ws/global")
async def websocket_global(websocket: WebSocket):
    if not await _verify_ws_token(websocket):
        return
    await ws_manager.connect(websocket)
    try:
        await websocket.send_json({
            "type": "connected",
            "message": "全局WebSocket连接成功"
        })
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)

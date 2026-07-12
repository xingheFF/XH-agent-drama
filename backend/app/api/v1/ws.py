import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from app.core.ws import ws_manager
from app.services.auth_service import decode_access_token

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


@router.websocket("/ws/canvas/{canvas_id}")
async def websocket_canvas(websocket: WebSocket, canvas_id: str):
    if not await _verify_ws_token(websocket):
        return
    await ws_manager.connect(websocket, canvas_id=canvas_id)
    try:
        await ws_manager.send_to_canvas(canvas_id, {
            "type": "connected",
            "canvas_id": canvas_id,
            "message": "WebSocket连接成功"
        })
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(data)
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, canvas_id=canvas_id)


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

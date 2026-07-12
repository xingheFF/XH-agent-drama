import logging
import mimetypes
import uuid
from typing import BinaryIO, Optional, Union

import requests
from qcloud_cos import CosConfig, CosS3Client

from app.core.config import settings

logger = logging.getLogger(__name__)


def _get_cos_client() -> CosS3Client:
    if not settings.TENCENT_COS_SECRET_ID or not settings.TENCENT_COS_SECRET_KEY:
        raise RuntimeError("请在 .env 中配置 TENCENT_COS_SECRET_ID 与 TENCENT_COS_SECRET_KEY")
    config = CosConfig(
        Region=settings.TENCENT_COS_REGION,
        SecretId=settings.TENCENT_COS_SECRET_ID,
        SecretKey=settings.TENCENT_COS_SECRET_KEY,
    )
    return CosS3Client(config)


def _ext_for_mime(content_type: str) -> str:
    ext = mimetypes.guess_extension(content_type.split(";")[0].strip())
    if ext:
        return ext.lstrip(".")
    mapping = {
        "video/mp4": "mp4",
        "image/webp": "webp",
        "image/png": "png",
        "image/jpeg": "jpg",
        "image/jpg": "jpg",
        "application/octet-stream": "bin",
        "binary/octet-stream": "bin",
    }
    return mapping.get(content_type.lower().split(";")[0].strip(), "bin")


def upload_to_cos(
    body: Union[bytes, BinaryIO],
    file_name: str,
    mime_type: str,
    content_length: Optional[int] = None,
) -> str:
    """上传 Buffer 或文件流到腾讯云 COS，返回 HTTPS 公网访问地址。"""
    client = _get_cos_client()
    if not settings.TENCENT_COS_BUCKET or not settings.TENCENT_COS_REGION:
        raise RuntimeError("请在 .env 中配置 TENCENT_COS_BUCKET 与 TENCENT_COS_REGION")

    size_desc = (
        len(body)
        if isinstance(body, (bytes, bytearray))
        else (content_length if content_length is not None else "unknown")
    )
    logger.info(
        "[COS] uploadToCos called: file_name=%s mime=%s size=%s bucket=%s region=%s",
        file_name,
        mime_type,
        size_desc,
        settings.TENCENT_COS_BUCKET,
        settings.TENCENT_COS_REGION,
    )

    params = {
        "Bucket": settings.TENCENT_COS_BUCKET,
        "Key": file_name,
        "Body": body,
        "ContentType": mime_type,
    }
    # bytes 类型 SDK 能自动推断长度，无需传 ContentLength
    # 流类型才需要显式指定，且必须转为字符串（httplib 要求 header 值为 str）
    if content_length is not None and not isinstance(body, (bytes, bytearray)):
        params["ContentLength"] = str(content_length)

    try:
        resp = client.put_object(**params)
    except Exception as exc:
        logger.error("COS Upload Error: %s", exc)
        raise RuntimeError(f"COS上传失败: {exc}") from exc

    location = resp.get("Location") if isinstance(resp, dict) else None
    if not location:
        location = (
            f"{settings.TENCENT_COS_BUCKET}.cos.{settings.TENCENT_COS_REGION}."
            f"myqcloud.com/{file_name}"
        )
    url = f"https://{location}"
    logger.info("[COS] Upload success: %s", url)
    return url


def cache_url_to_cos(url: str, prefix: str = "cache") -> Optional[str]:
    """从 URL 下载并转存到 COS，已经是 COS 地址则直接返回。"""
    if not url or "myqcloud.com" in url:
        return url

    logger.info("[COS] Starting cache for URL: %s", url)
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        )
    }

    try:
        response = requests.get(url, stream=True, timeout=60, headers=headers)
        response.raise_for_status()

        content_type = response.headers.get("content-type") or "application/octet-stream"
        if content_type.lower() in ("application/octet-stream", "binary/octet-stream"):
            url_ext = url.split("?")[0].split(".")[-1].lower()
            corrected = mimetypes.guess_type(f"x.{url_ext}")[0]
            if corrected:
                content_type = corrected

        content_length_header = response.headers.get("content-length")
        content_length = (
            int(content_length_header)
            if content_length_header and content_length_header.isdigit()
            else None
        )

        body_input = response.raw
        final_length = content_length

        # 缺失 Content-Length 时降级为 Buffer 模式，避免 SDK 流式上传异常
        if final_length is None:
            logger.warning("[COS] Missing Content-Length header, falling back to buffering")
            buffer_response = requests.get(url, timeout=60, headers=headers)
            buffer_response.raise_for_status()
            body_input = buffer_response.content
            final_length = len(body_input)
            if content_type == "application/octet-stream":
                ct = buffer_response.headers.get("content-type")
                if ct:
                    content_type = ct

        ext = _ext_for_mime(content_type)
        file_name = f"{prefix}/{uuid.uuid4()}.{ext}"
        cos_url = upload_to_cos(body_input, file_name, content_type, final_length)
        logger.info("[COS] Successfully cached to: %s", cos_url)
        return cos_url

    except Exception as exc:
        logger.error("[COS] Failed to cache URL to COS (%s): %s", url, exc)
        return None

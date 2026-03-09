from __future__ import annotations
"""
Download File Tool
httpx ile async dosya indirme — streaming, boyut limiti, timeout desteği.
"""

from langchain_core.tools import tool
from pydantic import BaseModel
import httpx
import logging

logger = logging.getLogger(__name__)


class DownloadFileInput(BaseModel):
    """download_file tool'u için giriş şeması."""
    url: str
    timeout: int = 30
    max_size_mb: float = 50.0


@tool(args_schema=DownloadFileInput)
async def download_file(
    url: str,
    timeout: int = 30,
    max_size_mb: float = 50.0,
) -> dict:
    """
    Belirtilen URL'den dosyayı indirir. Timeout ve boyut limiti kontrolü yapar.
    Büyük dosyalar için streaming indirme kullanır. İndirme başarısız olursa
    açıklayıcı hata mesajı döndürür (network hatası, 404, boyut aşımı vb.).

    Deterministic output alanları:
        success: bool
        content: bytes | None — Dosyanın ham byte içeriği
        content_type: str — HTTP Content-Type header
        size_bytes: int — İndirilen dosya boyutu
        error: str | None — Hata mesajı

    Bu tool side-effect olarak diske yazmaz; byte'ları memory'de döndürür.
    Timeout: Parametre ile kontrol edilir (varsayılan 30s).
    Retry: Bu tool kendi içinde retry yapmaz; çağıran taraf yönetir.
    """
    max_size_bytes = int(max_size_mb * 1024 * 1024)

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8",
    }

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            follow_redirects=True,
            headers=headers,
        ) as client:
            # HEAD request ile önce boyut kontrol et
            try:
                head_resp = await client.head(url)
                content_length = int(head_resp.headers.get("content-length", 0))
                if content_length > max_size_bytes:
                    return {
                        "success": False,
                        "content": None,
                        "content_type": "",
                        "size_bytes": content_length,
                        "error": (
                            f"Dosya çok büyük: {content_length / 1024 / 1024:.1f}MB "
                            f"(limit: {max_size_mb}MB)"
                        ),
                    }
            except Exception:
                pass  # HEAD desteklenmiyorsa devam et

            # Streaming GET
            content = b""
            content_type = "application/octet-stream"

            async with client.stream("GET", url) as response:
                response.raise_for_status()
                content_type = response.headers.get(
                    "content-type", "application/octet-stream"
                )

                async for chunk in response.aiter_bytes(chunk_size=8192):
                    content += chunk
                    if len(content) > max_size_bytes:
                        return {
                            "success": False,
                            "content": None,
                            "content_type": content_type,
                            "size_bytes": len(content),
                            "error": (
                                f"Dosya indirme sırasında boyut limitini "
                                f"({max_size_mb}MB) aştı"
                            ),
                        }

        logger.info(f"İndirme başarılı: {url} — {len(content)} bytes")

        return {
            "success": True,
            "content": content,
            "content_type": content_type,
            "size_bytes": len(content),
            "error": None,
        }

    except httpx.TimeoutException:
        return {
            "success": False,
            "content": None,
            "content_type": "",
            "size_bytes": 0,
            "error": f"Timeout: {timeout}s içinde yanıt alınamadı",
        }
    except httpx.HTTPStatusError as e:
        return {
            "success": False,
            "content": None,
            "content_type": "",
            "size_bytes": 0,
            "error": f"HTTP {e.response.status_code}: {url}",
        }
    except Exception as e:
        logger.error(f"İndirme hatası: {url} — {type(e).__name__}: {str(e)}")
        return {
            "success": False,
            "content": None,
            "content_type": "",
            "size_bytes": 0,
            "error": f"İndirme hatası: {type(e).__name__}: {str(e)}",
        }

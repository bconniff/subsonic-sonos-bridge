import logging

from aiohttp import ClientResponse, ClientSession, ClientTimeout
from fastapi import Request
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

REQUEST_HEADERS = {
    "range",
    "if-none-match",
    "if-modified-since",
}

RESPONSE_HEADERS = {
    "content-range",
    "content-length",
    "accept-ranges",
    "cache-control",
    "etag",
    "last-modified",
    "expires",
}

CHUNK_SIZE = 65536

TIMEOUT = ClientTimeout(
    total = None,
    connect = 10,
    sock_read = 30,
)

def _filter(headers, keep):
    return {k: v for k, v in headers.items() if k.lower() in keep}

class Streamer:
    def __init__(self):
        self._session = ClientSession(timeout = TIMEOUT)
        self._open: set[ClientResponse] = set()

    async def fetch(self, req: Request, url: str, params: dict | None = None) -> ClientResponse:
        return await self._session.request(
            req.method,
            url,
            params = params,
            headers = _filter(req.headers, REQUEST_HEADERS),
        )

    def respond(self, res: ClientResponse) -> StreamingResponse:
        async def body():
            self._open.add(res)
            logger.info("stream open %s open=%d", res.url.path, len(self._open))
            try:
                async for chunk in res.content.iter_chunked(CHUNK_SIZE):
                    yield chunk
            finally:
                res.close()
                self._open.discard(res)
                logger.info("stream close %s open=%d", res.url.path, len(self._open))

        return StreamingResponse(
            body(),
            status_code = res.status,
            media_type = res.headers.get("content-type"),
            headers = _filter(res.headers, RESPONSE_HEADERS),
        )

    async def close(self):
        await self._session.close()

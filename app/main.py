import logging

from starlette.concurrency import run_in_threadpool
from aiohttp import ClientResponse, ClientTimeout
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse, JSONResponse

from .context import (
    DependSubsonicAPI,
    DependHttpSession,
    DependSonosConnection,
    lifespan
)

from .model.request import PlayRequest, SearchRequest
from .sonos import SonosConnection

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)

app = FastAPI(title="subsonic-sonos-bridge", lifespan=lifespan)

PROXY_REQUEST_HEADERS = {
    "range",
    "if-none-match",
    "if-modified-since",
}

PROXY_RESPONSE_HEADERS = {
    "content-range",
    "content-length",
    "accept-ranges",
    "cache-control",
    "etag",
    "last-modified",
    "expires",
}

STREAM_CHUNK_SIZE = 65536

STREAM_TIMEOUT = ClientTimeout(
    total = None,
    sock_connect = 10,
    sock_read = 30,
)

class AppException(HTTPException):
    def __init__(self, status_code: int, detail: str, data = None):
        super().__init__(status_code=status_code, detail=detail)
        self.data = data

def _proxy_headers(headers, keep_headers=PROXY_RESPONSE_HEADERS):
    return {
        k: v for k, v in headers.items()
        if k.lower() in keep_headers
    }

def _stream_response(res: ClientResponse) -> StreamingResponse:
    async def body():
        async for chunk in res.content.iter_chunked(STREAM_CHUNK_SIZE):
            yield chunk
        await res.release()

    return StreamingResponse(
        body(),
        status_code = res.status,
        media_type = res.headers.get("content-type"),
        headers = _proxy_headers(res.headers),
    )

@app.exception_handler(AppException)
async def app_exception_handler(request, exc: AppException):
    return JSONResponse(
        status_code=exc.status_code,
        content = {
            key: value
            for key,value in {
                "detail": exc.detail,
                "data": exc.data,
            }.items()
            if value is not None
        },
        headers = exc.headers,
    )

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/search")
async def search(req: SearchRequest, subsonic: DependSubsonicAPI):
    return await subsonic.search(req)

@app.api_route("/stream/{id}", methods=['GET','HEAD'])
async def get_song_stream(id: str, req: Request, subsonic: DependSubsonicAPI, http: DependHttpSession):
    url, params = subsonic.get_stream_url(id)

    stream_res = await http.get(
        url,
        params = params,
        headers = _proxy_headers(req.headers, PROXY_REQUEST_HEADERS),
        timeout = STREAM_TIMEOUT,
    )

    if stream_res.headers.get('content-type') == 'application/json':
        json = await stream_res.json()
        raise AppException(404, 'Stream not found', json)

    return _stream_response(stream_res)

@app.api_route("/art/{id}", methods=['GET','HEAD'])
async def get_art(id: str, subsonic: DependSubsonicAPI):
    art_res = await subsonic.get_art(id)
    if not art_res:
        raise AppException(404, 'Art not found')
    return _stream_response(art_res)

@app.get("/sonos/{sonos_name}")
async def get_sonos_info(sonos_name: str, sonos: DependSonosConnection):
    device = await run_in_threadpool(sonos.get_device, sonos_name)
    if not device:
        raise AppException(404, 'Device not found')
    return await run_in_threadpool(device.get_info)

@app.get("/sonos/{sonos_name}/queue")
async def get_sonos_queue(sonos_name: str, sonos: DependSonosConnection):
    device = await run_in_threadpool(sonos.get_device, sonos_name)
    if not device:
        raise AppException(404, 'Device not found')
    return await run_in_threadpool(device.get_queue)

@app.post("/sonos/{sonos_name}/play")
async def play(sonos_name: str, req: PlayRequest, subsonic: DependSubsonicAPI, sonos: DependSonosConnection):
    songs_async = subsonic.resolve_songs(req)
    device = await run_in_threadpool(sonos.get_device, sonos_name)
    songs = await songs_async

    if not device:
        raise AppException(404, 'Device not found')
    if not songs:
        raise AppException(404, 'Songs not found')

    return await run_in_threadpool(device.play_songs, songs, req.mode)

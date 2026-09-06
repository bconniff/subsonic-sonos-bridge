import logging

from starlette.concurrency import run_in_threadpool
from aiohttp import ClientResponse
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse

from .context import (
    DependSubsonicAPI,
    DependHttpSession,
    DependSonosConnection,
    lifespan
)

from .models import PlayRequest, SearchRequest
from .sonos import SonosConnection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("subsonic-sonos-bridge")

app = FastAPI(title="subsonic-sonos-bridge", lifespan=lifespan)

PROXY_HEADERS = (
    "content-range",
    "content-length",
    "accept-ranges"
    "cache-control"
)

def proxy_headers(headers, keep_headers=PROXY_HEADERS):
    return {
        k: v for k, v in headers.items()
        if k.lower() in keep_headers
    }

def stream_response(res: ClientResponse) -> StreamingResponse:
    async def body():
        async for chunk in res.content:
            yield chunk
        res.release()

    return StreamingResponse(
        body(),
        status_code = res.status,
        media_type = res.headers.get("content-type"),
        headers = proxy_headers(res.headers),
    )

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/search")
async def search(req: SearchRequest, subsonic: DependSubsonicAPI):
    albums = (await subsonic.find_albums(req.query)) or []
    return [
        a for a in albums
        if req.matches(a)
    ]

@app.get("/album/{id}")
async def get_album(id: str, subsonic: DependSubsonicAPI):
    return await subsonic.get_album(id);

@app.get("/song/{id}")
async def get_stream(id: str, req: Request, subsonic: DependSubsonicAPI, http: DependHttpSession):
    url, params = subsonic.get_stream_url(id)

    return stream_response(await http.get(
        url,
        params = params,
        headers = proxy_headers(req.headers, ("ranges"))
    ))

@app.get("/art/{id}")
async def get_art(id: str, subsonic: DependSubsonicAPI):
    return stream_response(await subsonic.get_art(id))

@app.post("/play")
async def play(req: PlayRequest, subsonic: DependSubsonicAPI, sonos: DependSonosConnection):
    album_async = subsonic.get_album(req.album_id)
    device = sonos.get_device(req.sonos_name)
    album = await album_async

    if device is None:
        return None

    return await run_in_threadpool(device.queue_album, album)

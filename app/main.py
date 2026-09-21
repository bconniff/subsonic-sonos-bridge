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

def _proxy_headers(headers, keep_headers=PROXY_RESPONSE_HEADERS):
    return {
        k: v for k, v in headers.items()
        if k.lower() in keep_headers
    }

def _stream_response(res: ClientResponse) -> StreamingResponse:
    async def body():
        async for chunk in res.content:
            yield chunk
        await res.release()

    return StreamingResponse(
        body(),
        status_code = res.status,
        media_type = res.headers.get("content-type"),
        headers = _proxy_headers(res.headers),
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

    return _stream_response(await http.get(
        url,
        params = params,
        headers = _proxy_headers(req.headers, PROXY_REQUEST_HEADERS)
    ))

@app.api_route("/art/{id}", methods=['GET','HEAD'])
async def get_art(id: str, subsonic: DependSubsonicAPI):
    return _stream_response(await subsonic.get_art(id))

@app.get("/sonos/{sonos_name}")
async def get_sonos_info(sonos_name: str, sonos: DependSonosConnection):
    device = await run_in_threadpool(sonos.get_device, sonos_name)
    if not device:
        raise HTTPException(status_code = 404, detail = 'Device not found')
    return await run_in_threadpool(device.get_info)

@app.get("/sonos/{sonos_name}/queue")
async def get_sonos_queue(sonos_name: str, sonos: DependSonosConnection):
    device = await run_in_threadpool(sonos.get_device, sonos_name)
    if not device:
        raise HTTPException(status_code = 404, detail = 'Device not found')
    return await run_in_threadpool(device.get_queue)

@app.post("/sonos/{sonos_name}/play")
async def play(sonos_name: str, req: PlayRequest, subsonic: DependSubsonicAPI, sonos: DependSonosConnection):
    songs_async = subsonic.resolve_songs(req)
    device = await run_in_threadpool(sonos.get_device, sonos_name)
    songs = await songs_async

    if not device:
        raise HTTPException(status_code = 404, detail = 'Device not found')
    if not songs:
        raise HTTPException(status_code = 404, detail = 'Songs not found')

    return await run_in_threadpool(device.play_songs, songs, req.mode)

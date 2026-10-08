import logging

from starlette.concurrency import run_in_threadpool
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from .context import (
    DependSubsonicAPI,
    DependStreamer,
    DependSonosConnection,
    lifespan
)

from .model.request import PlayRequest, SearchRequest

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)

app = FastAPI(title="subsonic-sonos-bridge", lifespan=lifespan)

class AppException(HTTPException):
    def __init__(self, status_code: int, detail: str, data = None):
        super().__init__(status_code=status_code, detail=detail)
        self.data = data

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
async def get_song_stream(id: str, req: Request, subsonic: DependSubsonicAPI, streamer: DependStreamer):
    url, params = subsonic.get_stream_url(id)
    stream_res = await streamer.fetch(req, url, params)

    if stream_res.headers.get('content-type') == 'application/json':
        json = await stream_res.json()
        raise AppException(404, 'Stream not found', json)

    return streamer.respond(stream_res)

@app.api_route("/art/{id}", methods=['GET','HEAD'])
async def get_art(id: str, subsonic: DependSubsonicAPI, streamer: DependStreamer):
    art_res = await subsonic.get_art(id)
    if not art_res:
        raise AppException(404, 'Art not found')
    return streamer.respond(art_res)

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
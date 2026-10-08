from fastapi import FastAPI, Request, Depends
from contextlib import asynccontextmanager
from typing import Annotated
from asyncio import gather

from .streamer import Streamer
from .subsonic import SubsonicAPI
from .sonos import SonosConnection

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.subsonic_api = SubsonicAPI()
    app.state.streamer = Streamer()
    app.state.sonos_connection = SonosConnection()

    yield
    await gather(
        app.state.subsonic_api.close(),
        app.state.streamer.close(),
        app.state.sonos_connection.close(),
    )

def get_subsonic_api(req: Request) -> SubsonicAPI:
    return req.app.state.subsonic_api

def get_streamer(req: Request) -> Streamer:
    return req.app.state.streamer

def get_sonos_connection(req: Request) -> SonosConnection:
    return req.app.state.sonos_connection

DependSubsonicAPI = Annotated[SubsonicAPI, Depends(get_subsonic_api)]
DependStreamer = Annotated[Streamer, Depends(get_streamer)]
DependSonosConnection = Annotated[SonosConnection, Depends(get_sonos_connection)]
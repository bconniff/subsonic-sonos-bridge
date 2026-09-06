import os

from aiohttp import ClientSession
from fastapi import FastAPI, Request, Depends
from contextlib import asynccontextmanager
from typing import Annotated
from asyncio import gather

from .subsonic import SubsonicAPI
from .sonos import SonosConnection

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.subsonic_api = SubsonicAPI()
    app.state.http_session = ClientSession()
    app.state.sonos_connection = SonosConnection()
    yield
    await gather(
        app.state.subsonic_api.close(),
        app.state.http_session.close(),
        app.state.sonos_connection.close(),
    )

def get_subsonic_api(req: Request) -> SubsonicAPI:
    return req.app.state.subsonic_api

def get_http_session(req: Request) -> ClientSession:
    return req.app.state.http_session

def get_sonos_connection(req: Request) -> SonosConnection:
    return req.app.state.sonos_connection

DependSubsonicAPI = Annotated[SubsonicAPI, Depends(get_subsonic_api)]
DependHttpSession = Annotated[ClientSession, Depends(get_http_session)]
DependSonosConnection = Annotated[ClientSession, Depends(get_sonos_connection)]

from typing import Any
from enum import Enum
from pydantic import BaseModel

from .operations import Operation
from .matcher import build_query

class SearchRequestKind(str, Enum):
    SONG = 'song'
    ALBUM = 'album'
    PLAYLIST = 'playlist'

class PlayRequestMode(str, Enum):
    NORMAL = 'normal'
    NORMAL_REPEAT = 'normal_repeat'
    SHUFFLE = 'shuffle'
    SHUFFLE_REPEAT = 'shuffle_repeat'

class SearchRequest(BaseModel):
    query: str | None = None
    album: str | None = None
    album_id: str| None = None
    artist: str | None = None
    title: str | None = None
    year: int | None = None
    genre: str| None = None
    playlist: str | None = None
    playlist_id: str | None = None
    starred: bool | None = None
    kind: SearchRequestKind = SearchRequestKind.ALBUM
    ops: list[Operation] = []

    def build_query(self) -> str:
        search_fields = []
        match self.kind:
            case SearchRequestKind.ALBUM:
                search_fields = [
                    self.query,
                    self.album,
                    self.artist,
                ]
            case SearchRequestKind.SONG:
                search_fields = [
                    self.query,
                    self.album,
                    self.artist,
                    self.title,
                ]
            case SearchRequestKind.PLAYLIST:
                search_fields = [
                    self.query,
                    self.playlist,
                ]
        return build_query(*search_fields)

    def apply_ops(self, items: list[Any]) -> list[Any]:
        for op in self.ops:
            items = op.apply(items.copy())
        return items

class PlayRequest(SearchRequest):
    mode: PlayRequestMode = PlayRequestMode.NORMAL

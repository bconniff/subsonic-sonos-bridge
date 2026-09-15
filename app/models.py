import re

from collections import defaultdict
from random import sample
from itertools import islice
from enum import Enum

from pydantic import BaseModel

from .shuffle import constrained_shuffle

def _tokenize(a: str) -> list[str]:
    return re.findall(r"\w+", (a or "").casefold(), flags=re.UNICODE)

def _match_exact(a, b) -> bool:
    return a is None or a == b

def _match_eq(a: str, b: str) -> bool:
    return a is None or a.casefold() == (b or "").casefold()

def _match_in(a: str, b: list[str]) -> bool:
    return any(_match_eq(a, x) for x in (b or []))

def _match_fuzzy(a: str, b: str) -> bool:
    search_tokens = _tokenize(a)
    value_tokens = _tokenize(b)

    if not search_tokens:
        return True

    return all(
        any(value_token.startswith(search_token) for value_token in value_tokens)
        for search_token in search_tokens
    )

def _build_query(*parts: str | None) -> str:
    return " ".join(part for part in parts if part).strip()

class SearchRequestKind(str, Enum):
    SONG = 'song'
    ALBUM = 'album'
    PLAYLIST = 'playlist'

class SearchRequestOrder(str, Enum):
    NONE = 'none'
    NATURAL = 'natural'
    RANDOM = 'random'
    SMART = 'smart'

class PlayRequestMode(str, Enum):
    NORMAL = 'normal'
    NORMAL_REPEAT = 'normal_repeat'
    SHUFFLE = 'shuffle'
    SHUFFLE_REPEAT = 'shuffle_repeat'

class Sortable():
    def constraint_key(self):
        return ()
    def sort_key(self):
        return ()

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
    limit: int | None = None
    order_by: SearchRequestOrder = SearchRequestOrder.NONE
    kind: SearchRequestKind = SearchRequestKind.ALBUM

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
        return _build_query(*search_fields)

    def sort_results(self, items: list[Sortable]) -> list[Sortable]:
        limit = self.limit or len(items)

        match self.order_by:
            case SearchRequestOrder.RANDOM:
                return sample(items, limit)
            case SearchRequestOrder.SMART:
                return list(islice(constrained_shuffle(items, lambda x: x.constraint_key()), limit))
            case SearchRequestOrder.NATURAL:
                items = sorted(items, key = lambda x: x.sort_key())

        if limit < len(items):
            items = items[:limit]

        return items

class PlayRequest(SearchRequest):
    mode: PlayRequestMode = PlayRequestMode.NORMAL

class Matchable():
    def matches(self, req: SearchRequest) -> bool:
        return True

class AlbumInfo(BaseModel, Matchable, Sortable):
    album_id: str
    album: str
    artist_id: str
    artist: str
    genres: list[str]
    year: int | None
    cover_art: str | None
    starred: str | None

    def constraint_key(self):
        return (
            self.artist_id,
        )

    def sort_key(self):
        return (
            self.artist,
            self.year,
            self.album,
            self.album_id,
        )

    def search_string(self) -> str:
        return _build_query(
            self.album,
            self.artist,
        )

    def matches(self, req: SearchRequest) -> bool:
        return (
            _match_fuzzy(req.build_query(), self.search_string()) and
            _match_exact(req.year, self.year) and
            _match_eq(req.artist, self.artist) and
            _match_eq(req.album, self.album) and
            _match_exact(req.album_id, self.album_id) and
            _match_exact(req.starred, bool(self.starred)) and
            _match_in(req.genre, self.genres)
        )

class SongInfo(AlbumInfo):
    song_id: str
    album_artist: str
    content_type: str
    duration: int
    title: str
    track: int | None

    def sort_key(self):
        return (
            self.album_artist,
            self.year,
            self.album,
            self.album_id,
            self.track or 0,
            self.artist,
            self.title,
            self.song_id,
        )

    def search_string(self) -> str:
        return _build_query(
            super().search_string(),
            self.title,
        )

    def matches(self, req: SearchRequest) -> bool:
        return (
            super().matches(req) and
            _match_eq(req.title, self.title)
        )

class PlaylistInfo(BaseModel, Matchable, Sortable):
    playlist_id: str
    playlist: str

    def sort_key(self):
        return (
            self.playlist,
            self.playlist_id,
        )

    def search_string(self) -> str:
        return _build_query(
            self.playlist,
        )

    def matches(self, req: SearchRequest) -> bool:
        return (
            _match_fuzzy(req.build_query(), self.search_string()) and
            _match_eq(req.playlist, self.playlist) and
            _match_exact(req.playlist_id, self.playlist_id)
        )


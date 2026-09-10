import re
from enum import Enum
from pydantic import BaseModel

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

class PlayRequestMode(str, Enum):
    NORMAL = 'NORMAL'
    REPEAT_ONE = 'REPEAT_ONE'
    REPEAT_ALL = 'REPEAT_ALL'
    SHUFFLE = 'SHUFFLE'
    SHUFFLE_REPEAT_ONE = 'SHUFFLE_REPEAT_ONE'
    SHUFFLE_NOREPEAT = 'SHUFFLE_NOREPEAT'

class SearchRequest(BaseModel):
    query: str | None = None
    album: str | None = None
    artist: str | None = None
    title: str | None = None
    year: int | None = None
    genre: str| None = None
    playlist: str | None = None
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

class PlayRequest(SearchRequest):
    mode: PlayRequestMode = PlayRequestMode.NORMAL

class Matchable():
    def matches(req: SearchRequest) -> bool:
        return True

class AlbumInfo(BaseModel, Matchable):
    album_id: str
    album: str
    artist: str
    genres: list[str]
    year: int | None
    cover_art: str | None

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
            _match_in(req.genre, self.genres)
        )

class SongInfo(AlbumInfo):
    song_id: str
    content_type: str
    duration: int
    title: str
    track: int | None

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

class PlaylistInfo(BaseModel, Matchable):
    playlist_id: str
    playlist: str

    def search_string(self) -> str:
        return _build_query(
            self.playlist,
        )

    def matches(self, req: SearchRequest) -> bool:
        return (
            _match_fuzzy(req.build_query(), self.search_string()) and
            _match_eq(req.playlist, self.playlist)
        )


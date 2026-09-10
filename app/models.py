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

class AlbumInfo(BaseModel):
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

class SongInfo(AlbumInfo):
    song_id: str
    title: str
    track: int | None

    def search_string(self) -> str:
        return _build_query(
            super().search_string(),
            self.title,
        )

class PlaylistInfo(BaseModel):
    playlist_id: str
    playlist: str

class SearchRequest(BaseModel):
    query: str | None = None
    album: str | None = None
    artist: str | None = None
    title: str | None = None
    year: int | None = None
    genre: str| None = None
    playlist: str | None = None
    kind: SearchRequestKind = SearchRequestKind.ALBUM

    def build_album_query(self) -> str:
        return _build_query(
            self.query,
            self.album,
            self.artist,
        )

    def build_song_query(self) -> str:
        return _build_query(
            self.build_album_query(),
            self.title,
        )

    def match_album(self, it: AlbumInfo) -> bool:
        return (
            _match_fuzzy(self.build_album_query(), it.search_string()) and
            _match_exact(self.year, it.year) and
            _match_eq(self.artist, it.artist) and
            _match_eq(self.album, it.album) and
            _match_in(self.genre, it.genres)
        )

    def match_song(self, it: SongInfo) -> bool:
        return (
            self.match_album(it) and
            _match_eq(self.title, it.title)
        )

    def match_playlist(self, it: PlaylistInfo) -> bool:
        return (
            _match_fuzzy(self.query, it.playlist) and
            _match_eq(self.playlist, it.playlist)
        )

class PlayRequest(BaseModel):
    album_id: str | None = None
    playlist_id: str | None = None
    search: SearchRequest | None = None
    mode: PlayRequestMode = PlayRequestMode.NORMAL

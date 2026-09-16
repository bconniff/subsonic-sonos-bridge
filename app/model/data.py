from pydantic import BaseModel

from .request import SearchRequest
from .matcher import match_eq, match_in, match_exact, match_fuzzy, build_query

class BaseDataModel(BaseModel):
    def matches(self, req: SearchRequest) -> bool:
        return True

class AlbumData(BaseDataModel):
    album_id: str
    album: str
    artist_id: str
    artist: str
    genres: list[str]
    year: int | None
    cover_art: str | None
    starred: str | None

    def _search_string(self) -> str:
        return build_query(
            self.album,
            self.artist,
        )

    def matches(self, req: SearchRequest) -> bool:
        return (
            match_fuzzy(req.build_query(), self._search_string()) and
            match_exact(req.year, self.year) and
            match_eq(req.artist, self.artist) and
            match_eq(req.album, self.album) and
            match_exact(req.album_id, self.album_id) and
            match_exact(req.starred, bool(self.starred)) and
            match_in(req.genre, self.genres)
        )

class SongData(AlbumData):
    song_id: str
    album_artist: str
    content_type: str
    duration: int
    title: str
    track: int | None
    disc: int | None
    partition: int | None = None

    def _search_string(self) -> str:
        return build_query(
            super()._search_string(),
            self.title,
        )

    def matches(self, req: SearchRequest) -> bool:
        return (
            super().matches(req) and
            match_eq(req.title, self.title)
        )

class PlaylistData(BaseDataModel):
    playlist_id: str
    playlist: str

    def _search_string(self) -> str:
        return build_query(
            self.playlist,
        )

    def matches(self, req: SearchRequest) -> bool:
        return (
            match_fuzzy(req.build_query(), self._search_string()) and
            match_eq(req.playlist, self.playlist) and
            match_exact(req.playlist_id, self.playlist_id)
        )

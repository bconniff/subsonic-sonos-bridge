from pydantic import BaseModel

class SearchRequest(BaseModel):
    query: str
    album: str | None = None
    artist: str | None = None
    year: int | None = None

    def matches(self, it):
        return (
            (self.year is None or self.year == it.year) and
            (self.artist is None or self.artist == it.artist) and
            (self.album is None or self.artist == it.artist)
        )

class TrackIn(BaseModel):
    uri: str
    title: str
    artist: str | None = None
    album: str | None = None
    album_art_uri: str | None = None
    item_id: str | None = None


class PlayRequest(BaseModel):
    album_id: str | None = None
    playlist_id: str | None = None
    mode: str = "NORMAL"

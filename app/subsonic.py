import os

from libopensonic import AsyncConnection
from libopensonic.errors import DataNotFoundError

from .models import PlayRequest

class SubsonicAPI:
    def __init__(self):
        self.conn = AsyncConnection(
            base_url = os.environ.get('SUBSONIC_URL'),
            username = os.environ.get('SUBSONIC_USERNAME'),
            password = os.environ.get('SUBSONIC_PASSWORD'),
            port = os.environ.get('SUBSONIC_PORT', 443),
        )

    async def close(self):
        await self.conn.cleanup()

    async def find_playlists(self):
        return await self.conn.get_playlists()

    async def find_albums(self, query):
        result = await self.conn.search2(
            query = query,
            album_count = 10,
            artist_count = 0,
            song_count = 0,
        )
        return result.album or []

    async def get_playlist(self, id):
        try:
            return await self.conn.get_playlist(id)
        except DataNotFoundError:
            return None

    async def get_song(self, id):
        try:
            return await self.conn.get_song(id)
        except DataNotFoundError:
            return None

    async def get_album(self, id):
        try:
            return await self.conn.get_album(id)
        except DataNotFoundError:
            return None

    async def get_art(self, id):
        try:
            return await self.conn.get_cover_art(id)
        except DataNotFoundError:
            return None

    async def resolve_songs(self, req: PlayRequest):
        songs = []

        if req.album_id:
            album = await self.get_album(req.album_id)
            songs.extend(album.song if album else [])

        if req.playlist_id:
            playlist = await self.get_playlist(req.playlist_id)
            songs.extend(playlist.entry if playlist else [])

        return songs

    def get_stream_url(self, id):
        return self.conn.get_stream_url(id)

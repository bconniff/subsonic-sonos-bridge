import os

from libopensonic import AsyncConnection

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

    async def find_albums(self, query):
        result = await self.conn.search2(
            query = query,
            album_count = 10,
            artist_count = 0,
            song_count = 0,
        )
        return result.album

    async def get_album(self, id):
        return await self.conn.get_album(id)

    async def get_art(self, id):
        return await self.conn.get_cover_art(id)

    def get_stream_url(self, id):
        return self.conn.get_stream_url(id)

import os
import logging

from asyncio import gather, Semaphore

from libopensonic import AsyncConnection
from libopensonic.errors import DataNotFoundError

from .models import (
    PlayRequest,
    SearchRequest,
    SearchRequestKind,
    AlbumInfo,
    SongInfo,
    PlaylistInfo,
)

logger = logging.getLogger(__name__)

CONCURRENCY_LIMIT = 8
SEARCH_LIMIT = 1000
ALBUMS_LIMIT = 500

async def paginate(fetch_fn, extract_fn = lambda x: x, limit = SEARCH_LIMIT):
    offset = 0

    while True:
        page = extract_fn(await fetch_fn(limit, offset))

        for item in page:
            yield item

        if len(page) < limit:
            return

        offset += limit

def intersect_lists(id_fn, *lists):
    real_lists = [ l for l in lists if l is not None ]

    if not real_lists:
        return []

    retain_ids = set.intersection(*[
        { id_fn(item) for item in l }
        for l in real_lists
    ])

    return [
        item for item in real_lists[0]
        if id_fn(item) in retain_ids
    ]

def _to_album_info(it):
    return AlbumInfo(
        album_id = it.id,
        album = it.name,
        artist = it.artist,
        year = it.year,
        genres = [ genre.name for genre in it.genres ],
        cover_art = it.cover_art,
    )

def _to_song_info(it):
    return SongInfo(
        album_id = it.parent,
        album = it.album,
        artist = it.artist,
        year = it.year,
        genres = [ genre.name for genre in it.genres ],
        cover_art = it.cover_art,
        song_id = it.id,
        title = it.title,
        track = it.track,
    )

def _to_playlist_info(it):
    return PlaylistInfo(
        playlist_id = it.id,
        playlist = it.name,
    )

class SubsonicAPI:
    def __init__(self):
        self.conn = AsyncConnection(
            base_url = os.environ.get('SUBSONIC_URL'),
            username = os.environ.get('SUBSONIC_USERNAME'),
            password = os.environ.get('SUBSONIC_PASSWORD'),
            port = os.environ.get('SUBSONIC_PORT', 443),
        )
        self.semaphore = Semaphore(CONCURRENCY_LIMIT)

    async def close(self):
        await self.conn.cleanup()

    async def find_playlists(self):
        return await self.conn.get_playlists()

    async def _search_songs_by_query(self, req: SearchRequest) -> list[SongInfo]:
        query = req.build_song_query()

        logger.info('searching songs with search3')

        return [
            song async for song in paginate(
                lambda limit, offset: self.conn.search3(
                    query = query,
                    album_count = 0,
                    artist_count = 0,
                    song_count = limit,
                    song_offset = offset,
                ),
                lambda res: [ _to_song_info(it) for it in (res.song or []) ],
            )
            if req.match_song(song)
        ]

    async def _search_albums_by_query(self, req: SearchRequest) -> list[AlbumInfo]:
        query = req.build_album_query()

        logger.info('searching albums with search3')

        return [
            album async for album in paginate(
                lambda limit, offset: self.conn.search3(
                    query = query,
                    album_count = limit,
                    artist_count = 0,
                    song_count = 0,
                    album_offset = offset,
                ),
                lambda res: [ _to_album_info(it) for it in (res.album or []) ],
            )
            if req.match_album(album)
        ]

    async def _get_playlist_limited(self, id):
        async with self.semaphore:
            return await self.conn.get_playlist(id)

    async def _get_album_limited(self, id):
        async with self.semaphore:
            return await self.conn.get_album(id)

    async def _search_songs_by_playlist(self, req: SearchRequest) -> list[SongInfo]:
        logger.info('searching songs by playlist')

        playlists = await self.search_playlists(SearchRequest(
            playlist = req.playlist,
            kind = SearchRequestKind.PLAYLIST
        ))

        results = await gather(*(
            self._get_playlist_limited(p.playlist_id)
            for p in playlists
        ))

        songs = [ _to_song_info(it) for result in results for it in result.entry ]

        return [ song for song in songs if req.match_song(song) ]

    async def _search_albums_by_year(self, req: SearchRequest) -> list[AlbumInfo]:
        logger.info('searching albums by year')

        return [
            album async for album in paginate(
                lambda limit, offset: self.conn.get_album_list2(
                    ltype = 'byYear',
                    from_year = req.year,
                    to_year = req.year,
                    size = limit,
                    offset = offset,
                ),
                lambda res: [ _to_album_info(it) for it in res ],
                limit = ALBUMS_LIMIT,
            )
            if req.match_album(album)
        ]

    async def _search_albums_by_genre(self, req: SearchRequest) -> list[AlbumInfo]:
        logger.info('searching albums by genre')

        return [
            album async for album in paginate(
                lambda limit, offset: self.conn.get_album_list2(
                    ltype = 'byGenre',
                    genre = req.genre,
                    size = limit,
                    offset = offset,
                ),
                lambda res: [ _to_album_info(it) for it in res ],
                limit = ALBUMS_LIMIT,
            )
            if req.match_album(album)
        ]

    async def _search_songs_by_album(self, album_provider_fn, req: SearchRequest) -> list[SongInfo]:
        albums = await album_provider_fn(req)

        logger.info('searching songs by album')

        results = await gather(*(
            self._get_album_limited(album.album_id)
            for album in albums
        ))

        songs = [ _to_song_info(it) for result in results for it in result.song ]

        return [ song for song in songs if req.match_song(song) ]

    async def _search_songs_by_year(self, req: SearchRequest) -> list[SongInfo]:
        return await self._search_songs_by_album(self._search_albums_by_year, req)

    async def _search_songs_by_genre(self, req: SearchRequest) -> list[SongInfo]:
        return await self._search_songs_by_album(self._search_albums_by_genre, req)

    async def search_songs(self, req: SearchRequest) -> list[SongInfo]:
        if req.playlist:
            return await self._search_songs_by_playlist(req)
        if req.build_song_query():
            return await self._search_songs_by_query(req)
        if req.year:
            return await self._search_songs_by_year(req)
        if req.genre:
            return await self._search_songs_by_genre(req)
        return []


    async def search_albums(self, req: SearchRequest) -> list[AlbumInfo]:
        if req.build_album_query():
            return await self._search_albums_by_query(req)
        if req.year:
            return await self._search_albums_by_year(req)
        if req.genre:
            return await self._search_albums_by_genre(req)
        return []

    async def search_playlists(self, req: SearchRequest) -> list[PlaylistInfo]:
        result = await self.conn.get_playlists()
        playlists = [ _to_playlist_info(it) for it in (result or []) ]
        return [ it for it in playlists if req.match_playlist(it) ]

    async def search(self, req: SearchRequest):
        match req.kind:
            case SearchRequestKind.SONG:
                return await self.search_songs(req)
            case SearchRequestKind.ALBUM:
                return await self.search_albums(req)
            case SearchRequestKind.PLAYLIST:
                return await self.search_playlists(req)
        return []

    async def _get_or_none(self, coro):
        try:
            return await coro
        except DataNotFoundError:
            return None

    async def get_playlist(self, id):
        return await self._get_or_none(self.conn.get_playlist(id))

    async def get_song(self, id):
        return await self._get_or_none(self.conn.get_song(id))

    async def get_album(self, id):
        return await self._get_or_none(self.conn.get_album(id))

    async def get_art(self, id):
        return await self._get_or_none(self.conn.get_cover_art(id))

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

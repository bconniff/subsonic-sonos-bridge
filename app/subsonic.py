import os
import logging

from itertools import chain
from asyncio import gather, Semaphore

from libopensonic import AsyncConnection
from libopensonic.errors import DataNotFoundError

from .models import (
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
        content_type = it.content_type,
        duration = it.duration,
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

    async def _search_songs_by_query(self, req: SearchRequest) -> list[SongInfo]:
        logger.info('searching songs with search3 '+req.build_query())

        return [
            song async for song in paginate(
                lambda limit, offset: self.conn.search3(
                    query = req.build_query(),
                    album_count = 0,
                    artist_count = 0,
                    song_count = limit,
                    song_offset = offset,
                ),
                lambda res: [ _to_song_info(it) for it in (res.song or []) ],
            )
            if song.matches(req)
        ]

    async def _search_albums_by_query(self, req: SearchRequest) -> list[AlbumInfo]:
        logger.info('searching albums with search3')

        return [
            album async for album in paginate(
                lambda limit, offset: self.conn.search3(
                    query = req.build_query(),
                    album_count = limit,
                    artist_count = 0,
                    song_count = 0,
                    album_offset = offset,
                ),
                lambda res: [ _to_album_info(it) for it in (res.album or []) ],
            )
            if album.matches(req)
        ]

    async def _get_playlist_limited(self, id):
        async with self.semaphore:
            result = await self.conn.get_playlist(id)
            return [ _to_song_info(it) for it in result.entry ]

    async def _get_album_limited(self, id):
        async with self.semaphore:
            result = await self.conn.get_album(id)
            return [ _to_song_info(it) for it in result.song ]

    async def _get_playlists(self, playlists: list[PlaylistInfo]) -> list[SongInfo]:
        return list(chain.from_iterable(await gather(*(
            self._get_playlist_limited(p.playlist_id)
            for p in playlists
        ))))

    async def _get_albums(self, albums: list[AlbumInfo]) -> list[SongInfo]:
        return list(chain.from_iterable(await gather(*(
            self._get_album_limited(a.album_id)
            for a in albums
        ))))

    async def _search_songs_by_playlist(self, req: SearchRequest) -> list[SongInfo]:
        logger.info('searching songs by playlist')

        playlists = await self.search_playlists(SearchRequest(
            playlist = req.playlist,
            kind = SearchRequestKind.PLAYLIST
        ))
        songs = await self._get_playlists(playlists)
        return [ song for song in songs if song.matches(req) ]

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
            if album.matches(req)
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
            if album.matches(req)
        ]

    async def _search_songs_by_album(self, album_provider_fn, req: SearchRequest) -> list[SongInfo]:
        albums = await album_provider_fn(req)
        logger.info('searching songs by album')
        songs = await self._get_albums(albums)
        return [ song for song in songs if song.matches(req) ]

    async def _search_songs_by_year(self, req: SearchRequest) -> list[SongInfo]:
        return await self._search_songs_by_album(self._search_albums_by_year, req)

    async def _search_songs_by_genre(self, req: SearchRequest) -> list[SongInfo]:
        return await self._search_songs_by_album(self._search_albums_by_genre, req)

    async def _search_playlists_by_query(self, req: SearchRequest) -> list[PlaylistInfo]:
        result = await self.conn.get_playlists()
        playlists = [ _to_playlist_info(it) for it in (result or []) ]
        return [ it for it in playlists if it.matches(req) ]

    async def _search_songs(self, req: SearchRequest) -> list[SongInfo]:
        if req.playlist:
            return await self._search_songs_by_playlist(req)
        if req.build_query():
            return await self._search_songs_by_query(req)
        if req.year:
            return await self._search_songs_by_year(req)
        if req.genre:
            return await self._search_songs_by_genre(req)
        return []


    async def _search_albums(self, req: SearchRequest) -> list[AlbumInfo]:
        if req.build_query():
            return await self._search_albums_by_query(req)
        if req.year:
            return await self._search_albums_by_year(req)
        if req.genre:
            return await self._search_albums_by_genre(req)
        return []

    async def _search_playlists(self, req: SearchRequest) -> list[PlaylistInfo]:
        if req.build_query():
            return await self._search_playlists_by_query(req)
        return []

    async def search(self, req: SearchRequest):
        match req.kind:
            case SearchRequestKind.SONG:
                return await self._search_songs(req)
            case SearchRequestKind.ALBUM:
                return await self._search_albums(req)
            case SearchRequestKind.PLAYLIST:
                return await self._search_playlists(req)
        return []

    async def resolve_songs(self, req: SearchRequest) -> list[SongInfo]:
        songs = []
        results = await self.search(req)
        match req.kind:
            case SearchRequestKind.SONG:
                songs.extend(results)
            case SearchRequestKind.ALBUM:
                songs.extend(await self._get_albums(results))
            case SearchRequestKind.PLAYLIST:
                songs.extend(await self._get_playlists(results))
        return songs

    def get_stream_url(self, id):
        return self.conn.get_stream_url(id)

    async def get_art(self, id):
        return await self.conn.get_cover_art(id)

    async def close(self):
        await self.conn.cleanup()

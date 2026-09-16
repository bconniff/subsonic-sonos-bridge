import os
import logging

from itertools import chain
from asyncio import gather, Semaphore

from libopensonic import AsyncConnection
from libopensonic.errors import DataNotFoundError

from .model.request import SearchRequest, SearchRequestKind
from .model.data import AlbumData, SongData, PlaylistData

logger = logging.getLogger(__name__)

CONCURRENCY_LIMIT = 8
SEARCH_LIMIT = 1000
ALBUMS_LIMIT = 500

async def _paginate(fetch_fn, extract_fn = lambda x: x, limit = SEARCH_LIMIT):
    offset = 0

    while True:
        page = extract_fn(await fetch_fn(limit, offset))

        for item in page:
            yield item

        if len(page) < limit:
            return

        offset += limit

def _to_album_data(it):
    return AlbumData(
        album_id = it.id,
        album = it.name,
        artist_id = it.artist_id,
        artist = it.artist,
        year = it.year,
        genres = [ genre.name for genre in it.genres ],
        cover_art = it.cover_art,
        starred = it.starred,
    )

def _to_song_data(it):
    return SongData(
        album_id = it.parent,
        album = it.album,
        artist_id = it.artist_id,
        artist = it.artist,
        album_artist = it.display_album_artist,
        content_type = it.content_type,
        duration = it.duration,
        year = it.year,
        genres = [ genre.name for genre in it.genres ],
        cover_art = it.cover_art,
        song_id = it.id,
        title = it.title,
        track = it.track,
        disc = it.disc_number,
        starred = it.starred,
    )

def _to_playlist_data(it):
    return PlaylistData(
        playlist_id = it.id,
        playlist = it.name,
    )

def _filter_results(req: SearchRequest, res, to_data_fn = lambda x: x):
    infos = [ to_data_fn(it) for it in (res or []) ]
    return [ it for it in infos if it.matches(req) ]

class SubsonicAPI:
    def __init__(self):
        self.conn = AsyncConnection(
            base_url = os.environ.get('SUBSONIC_URL'),
            username = os.environ.get('SUBSONIC_USERNAME'),
            password = os.environ.get('SUBSONIC_PASSWORD'),
            port = os.environ.get('SUBSONIC_PORT', 443),
        )
        self.semaphore = Semaphore(CONCURRENCY_LIMIT)

    async def _get_playlist(self, id) -> list[SongData]:
        result = await self.conn.get_playlist(id)
        return [ _to_song_data(it) for it in result.entry ]

    async def _get_album(self, id) -> list[SongData]:
        result = await self.conn.get_album(id)
        return [ _to_song_data(it) for it in result.song ]

    async def _get_playlist_limited(self, id) -> list[SongData]:
        async with self.semaphore:
            return await self._get_playlist(id)

    async def _get_album_limited(self, id) -> list[SongData]:
        async with self.semaphore:
            return await self._get_album(id)

    async def _get_playlists(self, playlists: list[PlaylistData]) -> list[SongData]:
        return list(chain.from_iterable(await gather(*(
            self._get_playlist_limited(p.playlist_id)
            for p in playlists
        ))))

    async def _get_albums(self, albums: list[AlbumData]) -> list[SongData]:
        return list(chain.from_iterable(await gather(*(
            self._get_album_limited(a.album_id)
            for a in albums
        ))))

    async def _search_songs_by_starred(self, req: SearchRequest) -> list[SongData]:
        logger.info('searching songs by starred')
        res = await self.conn.get_starred2()
        return _filter_results(req, res.song, _to_song_data)

    async def _search_albums_by_starred(self, req: SearchRequest) -> list[AlbumData]:
        logger.info('searching albums by starred')
        res = await self.conn.get_starred2()
        return _filter_results(req, res.album, _to_album_data)

    async def _search_songs_by_query(self, req: SearchRequest) -> list[SongData]:
        logger.info('searching songs with search3')

        return [
            song async for song in _paginate(
                lambda limit, offset: self.conn.search3(
                    query = req.build_query(),
                    album_count = 0,
                    artist_count = 0,
                    song_count = limit,
                    song_offset = offset,
                ),
                lambda res: [ _to_song_data(it) for it in (res.song or []) ],
            )
            if song.matches(req)
        ]

    async def _search_albums_by_query(self, req: SearchRequest) -> list[AlbumData]:
        logger.info('searching albums with search3')

        return [
            album async for album in _paginate(
                lambda limit, offset: self.conn.search3(
                    query = req.build_query(),
                    album_count = limit,
                    artist_count = 0,
                    song_count = 0,
                    album_offset = offset,
                ),
                lambda res: [ _to_album_data(it) for it in (res.album or []) ],
            )
            if album.matches(req)
        ]

    async def _search_songs_by_playlist(self, req: SearchRequest) -> list[SongData]:
        logger.info('searching songs by playlist')
        playlists = await self.search(SearchRequest(
            playlist = req.playlist,
            playlist_id = req.playlist_id,
            kind = SearchRequestKind.PLAYLIST,
        ))
        songs = await self._get_playlists(playlists)
        return _filter_results(req, songs)

    async def _search_albums_by_year(self, req: SearchRequest) -> list[AlbumData]:
        logger.info('searching albums by year')

        return [
            album async for album in _paginate(
                lambda limit, offset: self.conn.get_album_list2(
                    ltype = 'byYear',
                    from_year = req.year,
                    to_year = req.year,
                    size = limit,
                    offset = offset,
                ),
                lambda res: [ _to_album_data(it) for it in res ],
                limit = ALBUMS_LIMIT,
            )
            if album.matches(req)
        ]

    async def _search_albums_by_genre(self, req: SearchRequest) -> list[AlbumData]:
        logger.info('searching albums by genre')

        return [
            album async for album in _paginate(
                lambda limit, offset: self.conn.get_album_list2(
                    ltype = 'byGenre',
                    genre = req.genre,
                    size = limit,
                    offset = offset,
                ),
                lambda res: [ _to_album_data(it) for it in res ],
                limit = ALBUMS_LIMIT,
            )
            if album.matches(req)
        ]

    async def _search_songs_by_album(self, album_provider_fn, req: SearchRequest) -> list[SongData]:
        albums = await album_provider_fn(req)
        logger.info('searching songs by album')
        songs = await self._get_albums(albums)
        return _filter_results(req, songs)

    async def _search_songs_by_year(self, req: SearchRequest) -> list[SongData]:
        return await self._search_songs_by_album(self._search_albums_by_year, req)

    async def _search_songs_by_genre(self, req: SearchRequest) -> list[SongData]:
        return await self._search_songs_by_album(self._search_albums_by_genre, req)

    async def _search_playlists_by_query(self, req: SearchRequest) -> list[PlaylistData]:
        result = await self.conn.get_playlists()
        return _filter_results(req, result, _to_playlist_data)

    async def _search_by_id(self, req: SearchRequest, fetch_fn, to_data_fn = lambda x: x):
        logger.info('searching by specific item id')
        items = []
        try:
            result = await fetch_fn()
            items = to_data_fn(result)
        except DataNotFoundError:
            pass
        return _filter_results(req, items)

    async def _search_playlists_by_id(self, req: SearchRequest) -> list[PlaylistData]:
        return await self._search_by_id(
            req,
            lambda: self.conn.get_playlist(req.playlist_id),
            lambda res: [ _to_playlist_data(res) ]
        )

    async def _search_albums_by_id(self, req: SearchRequest) -> list[AlbumData]:
        return await self._search_by_id(
            req,
            lambda: self.conn.get_album(req.album_id),
            lambda res: [ _to_album_data(res) ]
        )

    async def _search_songs_by_playlist_id(self, req: SearchRequest) -> list[SongData]:
        return await self._search_by_id(req, lambda: self._get_playlist(req.playlist_id))

    async def _search_songs_by_album_id(self, req: SearchRequest) -> list[SongData]:
        return await self._search_by_id(req, lambda: self._get_album(req.album_id))

    async def _search_songs(self, req: SearchRequest) -> list[SongData]:
        if req.album_id:
            return await self._search_songs_by_album_id(req)
        if req.playlist_id:
            return await self._search_songs_by_playlist_id(req)
        if req.playlist:
            return await self._search_songs_by_playlist(req)
        if req.starred:
            return await self._search_songs_by_starred(req)
        if req.build_query():
            return await self._search_songs_by_query(req)
        if req.year:
            return await self._search_songs_by_year(req)
        if req.genre:
            return await self._search_songs_by_genre(req)

        logger.warning('no searcher found for song query')
        return []

    async def _search_albums(self, req: SearchRequest) -> list[AlbumData]:
        if req.album_id:
            return await self._search_albums_by_id(req)
        if req.starred:
            return await self._search_albums_by_starred(req)
        if req.build_query():
            return await self._search_albums_by_query(req)
        if req.year:
            return await self._search_albums_by_year(req)
        if req.genre:
            return await self._search_albums_by_genre(req)

        logger.warning('no searcher found for album query')
        return []

    async def _search_playlists(self, req: SearchRequest) -> list[PlaylistData]:
        if req.playlist_id:
            return await self._search_playlists_by_id(req)
        if req.build_query():
            return await self._search_playlists_by_query(req)

        logger.warning('no searcher found for playlist query')
        return []

    async def _search_unsorted(self, req: SearchRequest):
        match req.kind:
            case SearchRequestKind.SONG:
                return await self._search_songs(req)
            case SearchRequestKind.ALBUM:
                return await self._search_albums(req)
            case SearchRequestKind.PLAYLIST:
                return await self._search_playlists(req)

        logger.warning('unknown search kind')
        return []

    async def search(self, req: SearchRequest):
        return req.apply_ops(await self._search_unsorted(req))

    async def resolve_songs(self, req: SearchRequest) -> list[SongData]:
        results = await self.search(req)
        match req.kind:
            case SearchRequestKind.ALBUM:
                results = await self._get_albums(results)
            case SearchRequestKind.PLAYLIST:
                results = await self._get_playlists(results)
        return results

    def get_stream_url(self, id):
        return self.conn.get_stream_url(id)

    async def get_art(self, id):
        return await self.conn.get_cover_art(id)

    async def close(self):
        await self.conn.cleanup()

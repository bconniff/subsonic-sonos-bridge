import os
import re

from asyncio import gather

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

SEARCH_LIMIT = 1000

def intersect_lists(id_fn, *lists):
    real_lists = [ l for l in lists if l is not None ]

    retain_ids = set.intersection(*[
        { id_fn(item) for item in l }
        for l in real_lists
    ]) if real_lists else set()

    return list({
        id_fn(s): s
        for s in real_lists[0]
        if id_fn(s) in retain_ids
    }.values()) if real_lists else []


async def paginate(fetch_fn, extract_fn, filter_fn, limit = SEARCH_LIMIT):
    results = []
    offset = 0
    done = False

    while not done:
        page = extract_fn(await fetch_fn(limit, offset))
        results.extend(it for it in page if filter_fn(it))
        offset += limit
        done = len(page) < limit

    return results

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

    async def search_albums(self, req: SearchRequest) -> list[AlbumInfo]:
        query = " ".join(
            x for x in [
                req.query,
                req.album,
                req.artist,
            ]
            if x is not None
        ).strip()

        albums = []

        if query:
            albums = await paginate(
                lambda limit, offset: self.conn.search3(
                    query = query,
                    album_count = limit,
                    artist_count = 0,
                    song_count = 0,
                    album_offset = offset,
                ),
                lambda res: [
                    AlbumInfo(
                        album_id = it.id,
                        album = it.name,
                        artist = it.artist,
                        year = it.year,
                        genres = [ genre.name for genre in it.genres ],
                        cover_art = it.cover_art,
                    )
                    for it in (res.album or [])
                ],
                req.match_album
            )

        return albums

    async def _search_songs_query(self, req: SearchRequest) -> list[SongInfo]:
        query = " ".join(
            x for x in [
                req.query,
                req.album,
                req.artist,
                req.title,
            ]
            if x is not None
        ).strip()

        if not query:
            return None

        return await paginate(
            lambda limit, offset: self.conn.search3(
                query = query,
                album_count = 0,
                artist_count = 0,
                song_count = limit,
                song_offset = offset,
            ),
            lambda res: [
                SongInfo(
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
                for it in (res.song or [])
            ],
            req.match_song
        )

    async def _search_songs_playlist(self, req: SearchRequest) -> list[SongInfo]:
        if not req.playlist:
            return None

        playlists = await self.search_playlists(SearchRequest(
            playlist = req.playlist,
            kind = SearchRequestKind.PLAYLIST
        ))

        results = await gather(*(
            self.conn.get_playlist(p.playlist_id)
            for p in playlists
        ))

        songs = [
            SongInfo(
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
            for result in results
            for it in result.entry
        ]

        return [ song for song in songs if req.match_song(song) ]

    async def search_songs(self, req: SearchRequest) -> list[SongInfo]:
        searches = await gather(*(
            self._search_songs_playlist(req),
            self._search_songs_query(req),
        ))

        return intersect_lists(lambda s: s.song_id, *searches)

    async def search_playlists(self, req: SearchRequest) -> list[PlaylistInfo]:
        result = await self.conn.get_playlists()
        playlists = [
            PlaylistInfo(
                playlist_id = it.id,
                playlist = it.name,
            )
            for it in (result or [])
        ]
        return [ it for it in playlists if req.match_playlist(it) ]

    async def search(self, req: SearchRequest):
        match req.kind:
            case SearchRequestKind.SONG.value:
                return await self.search_songs(req)
            case SearchRequestKind.ALBUM.value:
                return await self.search_albums(req)
            case SearchRequestKind.PLAYLIST.value:
                return await self.search_playlists(req)
        return []

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

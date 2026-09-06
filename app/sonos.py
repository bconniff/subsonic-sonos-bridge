import os
import re
import time

from collections import deque
from soco import SoCo, discovery
from soco.data_structures import DidlMusicTrack, DidlResource

def format_duration(seconds: int) -> str:
    h, remainder = divmod(seconds, 3600)
    m, s = divmod(remainder, 60)
    return f"{h}:{m:02d}:{s:02d}"

class SonosDevice:
    def __init__(self, name):
        self.bridge_url = os.environ.get("BRIDGE_URL", "http://localhost:8000")

        if re.fullmatch(r"\d+\.\d+\.\d+\.\d+", name):
            self.soco = SoCo(name)
        else:
            self.soco = discovery.by_name(name)

        if self.soco is None:
            raise ValueError(f"Speaker not found: {name}")

        self.name = self.soco.player_name
        self.ip = self.soco.ip_address

    def queue_track(self, song):
        track_didl = DidlMusicTrack(
            title = song.title,
            parent_id = song.parent,
            item_id = song.id,
            creator = song.artist or "",
            album = song.album or "",
            album_art_uri = f"{self.bridge_url}/art/{song.cover_art}",
            resources = [
                DidlResource(
                    uri = f"{self.bridge_url}/song/{song.id}",
                    protocol_info = f"http-get:*:{song.content_type}:*",
                    duration = format_duration(song.duration),
                )
            ],
        )
        self.soco.add_to_queue(track_didl)
        return track_didl

    def queue_album(self, album):
        results = []

        if album.song:
            songs = deque(album.song)

            self.soco.clear_queue()
            self.soco.play_mode = "NORMAL"

            self.queue_track(songs.popleft())
            self.soco.play_from_queue(0)

            for song in songs:
                result = self.queue_track(song)
                results.append(result)

        return results

class SonosConnection:
    devices = {}

    def get_device(self, name):
        device = self.devices.get(name)

        if device is None:
            try:
                device = SonosDevice(name)
            except ValueError:
                pass

        if device is not None:
            self.devices[device.name] = device
            self.devices[device.ip] = device

        return device

    async def close(self):
        pass

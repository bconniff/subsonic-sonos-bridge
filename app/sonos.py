import os
import re

from soco import SoCo, discovery
from soco.data_structures import DidlMusicTrack, DidlResource

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
        track = DidlMusicTrack(
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
                )
            ],
        )
        return track

    def queue_album(self, album):
        results = []
        for s in album.song:
            results.append(self.queue_track(s))
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

    def close(self):
        pass

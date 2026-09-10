import logging
import os
import re
import time

from collections import deque
from soco import SoCo, discovery
from soco.data_structures import DidlMusicTrack, DidlResource, to_didl_string

from .models import PlayRequestMode

logger = logging.getLogger(__name__)

# determines how many songs we queue before sending the "play queue" request
FIRST_BATCH_SIZE = 16

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

    def to_track_didls(self, songs):
        return [
            DidlMusicTrack(
                title = song.title,
                parent_id = "0",
                item_id = song.id,
                creator = song.artist or "",
                album = song.album or "",
                album_art_uri = f"{self.bridge_url}/art/{song.cover_art}",
                original_track_number = song.track,
                resources = [
                    DidlResource(
                        uri = f"{self.bridge_url}/song/{song.id}/stream",
                        protocol_info = f"http-get:*:{song.content_type}:*",
                        duration = format_duration(song.duration),
                    )
                ],
            )
            for song in songs
        ]

    def play_songs(self, songs, mode = PlayRequestMode.NORMAL):
        results = []

        if songs:
            coordinator = self.soco if self.soco.is_coordinator else self.soco.group.coordinator

            results = self.to_track_didls(songs)

            coordinator.clear_queue()
            coordinator.play_mode = mode.value

            head = results[:FIRST_BATCH_SIZE]
            tail = results[FIRST_BATCH_SIZE:]

            coordinator.add_multiple_to_queue(head)
            coordinator.play_from_queue(0)
            if tail:
                coordinator.add_multiple_to_queue(tail)

        return results

    def get_queue(self):
        return self.soco.get_queue()

    def get_info(self):
        coordinator = self.soco if self.soco.is_coordinator else self.soco.group.coordinator
        return {
            'ip': self.ip,
            'name': self.name,
            'is_coordinator': self.soco.is_coordinator,
            'play_mode': self.soco.play_mode,
            'available_actions': coordinator.available_actions,
            'music_source': self.soco.music_source,
            'group_coordinator': self.soco.group.coordinator.player_name,
            'track': self.soco.get_current_track_info(),
            'media': self.soco.get_current_media_info(),
            'speaker': self.soco.get_speaker_info(),
            'tx': self.soco.get_current_transport_info(),
            'queue_size': self.soco.queue_size,
        }

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

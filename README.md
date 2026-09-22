# Subsonic-Sonos Bridge

Simple Python FastAPI server to connect an OpenSubsonic server with Sonos.

## How it works

Uses py-opensonic to connect with a Subsonic server and SoCo to enqueue and
stream tracks of HTTP(S) to sonos via UPnP. I've only tested this with
Navidrome, but it likely works with other OpenSubsonic implementations.

## How to use it

Exposes a very simple API to control the bridge.

Some endpoint examples below, but you can also read `app/main.py`:

### POST /search

```sh
curl -XPOST --data-raw \
    -H 'Content-Type: application/json' \
    '{ "query": "Weezer", "year": 2016 }' \
    https://bridge.brendanconniff.com/search
```

```js
[
  {
    "partition": null,
    "album_id": "abcdef",
    "album": "Weezer",
    "artist_id": "abcdef",
    "artist": "Weezer",
    "genres": [ "Alternative Rock", "Rock" ],
    "year": 2016,
    "cover_art": "abcdef",
    "starred": null,
    "song_id": "abcdef",
    "album_artist": "Weezer",
    "content_type": "audio/mpeg",
    "duration": 205,
    "title": "(Girl We Got a) Good Thing",
    "track": 4,
    "disc": 1
  },
  ...
]
```


### GET /health

```sh
curl -G /health
```

```js
{ "status": "ok" }
```

### POST /sonos/{name}/play

Same request format as `POST /search`, but enqueues playback on the Sonos
speaker `{name}` with SoCo. Returns a list of the enqueued DIDL payloads.

## Environment

Some environment variables can be used to configure the bridge.

For example, you can run it behind a reverse proxy like Caddy to serve
everything over HTTPS, and configure Navidrome to transcode verything to
WAV audio and apply replaygain settings on the server side:

```sh
SUBSONIC_URL=https://music.example.com
SUBSONIC_USERNAME=hass
SUBSONIC_PASSWORD=pass
SUBSONIC_PORT=443
BRIDGE_URL=https://bridge.brendanconniff.com
FORCE_CONTENT_TYPE=audio/wav
```

## Docker

If you're using docker compose, add this:

```yaml
services:
  sonos-subsonic-bridge:
    container_name: sonos-subsonic-bridge
    build: .
    restart: unless-stopped
    network_mode: host
    environment:
      SUBSONIC_URL: 'https://music.brendanconniff.com'
      SUBSONIC_USERNAME: ${SUBSONIC_USERNAME}
      SUBSONIC_PASSWORD: ${SUBSONIC_PASSWORD}
```

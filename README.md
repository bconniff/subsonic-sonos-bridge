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
    https://bridge.example.com/search
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

Also accepts a mode parameter:

* normal
* normal\_repeat
* shuffle
* shuffle\_repeat

```sh
curl -XPOST --data-raw \
    -H 'Content-Type: application/json' \
    '{ "query": "Weezer", "year": 2016, "mode": "shuffle" }' \
    https://bridge.example.com/search
```

### Advanced operations

The `search` and `play` APIs accept an `ops` parameter that allows you to
transform the resorts by sorting or shuffling:

#### Sorting

Sorts fields in order. You may specify `asc` or `desc` to reverse the order:

```js
{
    "genre": "Indie Rock",
    "ops": [
        { "sort": [ "artist", "album", "year desc", "track asc" ] }
    ]
}
```

#### Shuffling

There are 3 shuffle modes supported: `random`, `constrained`, and `stable`

Random shuffling is the simplest, and just randomizes the result list:

```js
{
    "genre": "Indie Rock",
    "ops": [
        { "shuffle": "random" }
    ]
}
```

Constrained shuffling is the most complex, and applies a constrained softmax
shuffle to evenly distribute items while avoiding adjacency based on the
constrained fields:

```js
{
    "genre": "Indie Rock",
    "ops": [
        { "shuffle": "constrained", "by": [ "artist_id" ] }
    ]
}
```

And last, stable shuffling groups items together by common keys before
shuffling randomly. It's advisable to sort results first. For example, to
shuffle albums while maintaining track order:

```js
{
    "genre": "Indie Rock",
    "ops": [
        { "sort": "stable", "by": [ "artist", "album", "track" ] },
        { "shuffle": "stable", "by": [ "artist", "album" ] }
    ]
}
```

#### Partitioning

Partitioning applies an incrementing `partition` field any time one of the
partition fields changes. It's designed to be used with sorting/shuffling. For
example, to shuffle a playlist without splitting adjacent tracks from the same
album:

```js
{
    "playlist": "My Cool Playlist",
    "ops": [
        { "partition": [ "album_id" ] },
        { "shuffle": "stable", "by": [ "partition" ] }
    ]
}
```

#### Top

Limit results with `top`:

```js
{
    "playlist": "My Cool Playlist",
    "ops": [
        { "top": 10 }
    ]
}
```

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
BRIDGE_URL=https://bridge.example.com
FORCE_CONTENT_TYPE=audio/wav
```

## Docker

You can use a Dockerfile to install from a specific tag:

```dockerfile
FROM python:3-slim
RUN pip install --no-cache-dir https://github.com/bconniff/subsonic-sonos-bridge/archive/refs/tags/v1.0.0.tar.gz
USER nobody
CMD ["subsonic-sonos-bridge"]
```

And if you're using docker compose, add something this:

```yaml
services:
  sonos-subsonic-bridge:
    container_name: sonos-subsonic-bridge
    build: .
    restart: unless-stopped
    network_mode: host
    environment:
      SUBSONIC_URL: 'https://music.example.com'
      SUBSONIC_USERNAME: ${SUBSONIC_USERNAME}
      SUBSONIC_PASSWORD: ${SUBSONIC_PASSWORD}
```

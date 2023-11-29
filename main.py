import argparse
from pathlib import Path
import os
import shutil
import torch
import json

from scripts import get_title, download_and_split, get_musixmatch, get_whisper
from match_words import get_karaoke_lines

import asyncio
from concurrent.futures import ProcessPoolExecutor

from gql import Client, gql
from gql.transport.websockets import WebsocketsTransport
from gql.transport.aiohttp import AIOHTTPTransport

from gql.transport.appsync_auth import AppSyncApiKeyAuthentication

import boto3

# Uncomment these lines when using as a one off function called on command line (as opposed to a server)

# parser = argparse.ArgumentParser(description="Generates timestamped lyrics and a vocal-less karaoke track, given an English song with lyrics on Spotify.")
# parser.add_argument("-s", "--song", type=str, required=True, help="name of the song")
# parser.add_argument("-a", "--artists", type=str, nargs="+", required=True, help="space separated list of artists")
# parser.add_argument("-d", "--duration", type=float, required=True, help="duration of song in seconds")
# parser.add_argument("-i", "--id", type=str, required=True, help="Spotify track ID")

# args = parser.parse_args()

S3 = boto3.client("s3")
BUCKET = os.environ.get("S3_BUCKET_NAME")

# GraphQL Queries
SUBSCRIPTION = gql("""
subscription RequestedKaraoke {
  requestedKaraoke {
    name
    artists
    duration
    id
  }
}
""")
                   
MUTATION = gql("""
mutation AddKaraoke($id: String!, $lyrics: String!, $url: String!) {
  addKaraoke(id: $id, lyrics: $lyrics, url: $url) {
    id
  }
}
""")

def get_karaoke(name: str,
    artists: list[str],
    length: int,
    spotify_id: str,
    MAX_TIME_DIF: int = 2) -> (str, str):
    """Returns S3 key of the lyrics JSON and the URL to the karaoke wav file."""

    lyrics_key = spotify_id + "/lyrics.json"
    track_key = spotify_id + "/track.wav"

    # Check if the files already exist first, if so return them
    
    try: 
        print("Looking for existing files on S3...")
        S3.get_object(Bucket=BUCKET, Key=lyrics_key)
        S3.get_object(Bucket=BUCKET, Key=track_key)

        track_url = S3.generate_presigned_url("get_object", Params={"Bucket": BUCKET, "Key": track_key}, ExpiresIn=3600)

        return lyrics_key, track_url
    except Exception as e:
        print(e)
        pass

    title = get_title(name, artists)
    
    print("Creating directories...")
    # Make the necessary directories if they don't already exist
    pytube_dir = os.path.join(spotify_id, "pytube")
    Path(pytube_dir).mkdir(parents=True, exist_ok=True)

    spleeter_dir = os.path.join(spotify_id, "spleeter")
    Path(spleeter_dir).mkdir(parents=True, exist_ok=True)

    lyrics_dir = os.path.join(spotify_id, "lyrics", title)
    Path(lyrics_dir).mkdir(parents=True, exist_ok=True)

    print("Downloading from YouTube and splitting...")
    vocals, karaoke_track = download_and_split(title, length, pytube_dir, spleeter_dir)
    musixmatch = get_musixmatch(spotify_id, lyrics_dir)
    whisper = get_whisper(vocals, lyrics_dir)

    lyrics_json = get_karaoke_lines(musixmatch, whisper, lyrics_dir)

    print("Uploading lyric and karaoke track files...")
    # Upload voiceless accompaniment track and timestamped lyrics to S3
    S3.upload_file(lyrics_json, BUCKET, lyrics_key)
    S3.upload_file(karaoke_track, BUCKET, track_key)

    track_url = S3.generate_presigned_url("get_object", Params={"Bucket": BUCKET, "Key": track_key}, ExpiresIn=3600)
    # Delete temporary directory
    shutil.rmtree(spotify_id)
    print("Deleting temporary directory " + spotify_id + "...")
    
    return lyrics_key, track_url


async def add_karaoke_mutation(http_session, req):
    # Save temporary files for song in a folder in the container named after the unique spotify track ID
    # lyrics_key, karaoke_url = await loop.run_in_executor(p, get_karaoke, req["name"], req["artists"], req["duration"], req["id"])
    lyrics_key, karaoke_url = get_karaoke(req["name"], req["artists"], req["duration"], req["id"])

    local_lyrics_file = req["id"] + ".json"
    print("Downloading lyrics json...")
    S3.download_file(BUCKET, lyrics_key, local_lyrics_file)
    with open(local_lyrics_file, "r") as f:
        lyrics_json = json.load(f)

    lyrics_json_string = json.dumps(lyrics_json)
    mutation_vars = {"id": req["id"], "lyrics": lyrics_json_string, "url": karaoke_url}

    result = await http_session.execute(MUTATION, variable_values=mutation_vars)
    return result


async def main():
    API_URL = "https://spotify-karaoke-api-fabe17189228.herokuapp.com/"
    WS_URL = API_URL.replace("https://", "ws://").replace("/graphql", "")


    if torch.cuda.is_available():
        print("CUDA device detected, ignoring TF warnings about AVX...")
        os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

    realtime_transport = WebsocketsTransport(url=WS_URL)
    # http_transport = AIOHTTPTransport(url=API_URL, auth=realtime_transport.auth)
    http_transport = AIOHTTPTransport(url=API_URL)

    async with Client(transport=realtime_transport) as session:
        async with Client(transport=http_transport, fetch_schema_from_transport=False) as http_session:
            print("Waiting for messages...")

            async for result in session.subscribe(SUBSCRIPTION):
                print(result["requestedKaraoke"])

                task = asyncio.create_task(add_karaoke_mutation(http_session, result["requestedKaraoke"]))

loop = asyncio.get_event_loop()
# p = ProcessPoolExecutor(4)
loop.run_until_complete(main())

# get_karaoke(args.song, args.artists, args.duration, args.id)


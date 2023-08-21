import argparse
from pathlib import Path
import os
from scripts import download_and_split, get_musixmatch, get_whisper
from match_words import get_karaoke_lines

parser = argparse.ArgumentParser(description="Generates timestamped lyrics and a vocal-less karaoke track, given an English song with lyrics on Spotify.")
parser.add_argument("-s", "--song", type=str, required=True, help="name of the song")
parser.add_argument("-a", "--artists", type=str, nargs="+", required=True, help="space separated list of artists")
parser.add_argument("-d", "--duration", type=float, required=True, help="duration of song in seconds")
parser.add_argument("-i", "--id", type=str, required=True, help="Spotify track ID")
parser.add_argument("-o", "--output", type=str, required=True, help="output directory for saving downloaded files")

args = parser.parse_args()

def get_karaoke(name: str,
    artists: list[str],
    length: int,
    spotify_id: str,
    OUTPUT_DIR: str,
    MAX_TIME_DIF: int = 2):
    
    # Make the necessary directories if they don't already exist
    pytube_dir = os.path.join(OUTPUT_DIR, "pytube")
    Path(pytube_dir).mkdir(parents=True, exist_ok=True)

    spleeter_dir = os.path.join(OUTPUT_DIR, "spleeter")
    Path(spleeter_dir).mkdir(parents=True, exist_ok=True)

    lyrics_dir = os.path.join(OUTPUT_DIR, "lyrics")
    Path(lyrics_dir).mkdir(parents=True, exist_ok=True)

    vocals, karaoke_track = download_and_split(name, artists, length, pytube_dir, spleeter_dir)
    musixmatch = get_musixmatch(spotify_id, lyrics_dir)
    whisper = get_whisper(vocals, lyrics_dir)

    lyrics_json = get_karaoke_lines(musixmatch, whisper, lyrics_dir)

    return lyrics_json, karaoke_track

get_karaoke(args.song, args.artists, args.duration, args.id, args.output)
    
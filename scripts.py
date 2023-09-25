import re
import os
import whisperx
import json
import torch
import requests
from pathlib import Path
from typing import Tuple

from pytube import Search
from spleeter.separator import Separator

separator = Separator("spleeter:2stems")


def get_title(
    name: str,
    artists: list[str],
):
    # Create search query for song by combining artists' and song's names
    title = ""
    for artist in artists:
        title += artist + " "
    title += name

    # Filter out title to only be alphanumeric characters and replace spaces with hyphens
    alphanumeric = re.compile("[^a-zA-Z0-9_\s]+")
    white_space = re.compile("\s+")
    title = re.sub(alphanumeric, "", title)
    title = re.sub(white_space, "-", title)

    return title

def download_and_split(title, length: int, pytube_dir: str, spleeter_dir: str, MAX_TIME_DIF: int = 2) -> Tuple[str, str]:
    """Downloads a song from YouTube and splits into 2 stems. Returns path to vocals and accompaniment audio files."""

    vocals_path = os.path.join(spleeter_dir, title, "vocals.wav")
    accompaniment_path = os.path.join(spleeter_dir, title, "accompaniment.wav")

    if os.path.exists(vocals_path) and os.path.exists(accompaniment_path):
        print("Spleeter stem files already exist. Returning path.")
        return vocals_path, accompaniment_path

    s = Search(title)
    for video in s.results:
        # Search YouTube for first result matching search query that has a duration
        # within max_time_dif seconds of Spotify's listed duration for the song
        if abs(video.length - length) < MAX_TIME_DIF:
            streams = video.streams.filter(only_audio=True)

            song_path = os.path.join(pytube_dir, title)

            if not os.path.exists(song_path):
                print("Downloading to " + song_path)
                song_path = streams[0].download(pytube_dir, title)

            separator.separate_to_file(song_path, spleeter_dir)

            return vocals_path, accompaniment_path


def get_musixmatch(track_id: str, lyrics_dir: str):
    """Retrieves the musixmatch lyrics, downloads to a json file, and returns the path."""
    musixmatch_path = os.path.join(lyrics_dir, "musixmatch.json")

    if os.path.exists(musixmatch_path):
        print("Musixmatch lyrics json already exists. Returning path.")
        return musixmatch_path

    res = requests.get(f"https://spotify-lyric-api.herokuapp.com/?trackid={track_id}")
    musixmatch_lyrics = res.json()

    with open(musixmatch_path, "w") as f:
        json.dump(musixmatch_lyrics, f)
        print("Writing musixmatch lyrics json to " + musixmatch_path)

    return musixmatch_path


def get_whisper(speech_audio_file: str, lyrics_dir: str) -> str:
    whisper_path = os.path.join(lyrics_dir, "whisper.json")

    if os.path.exists(whisper_path):
        print("Whisper transcription json already exists. Returning path.")
        return whisper_path

    device = "cuda"
    batch_size = 16  # reduce if low on GPU mem
    compute_type = "float16"  # change to "int8" if low on GPU mem (may reduce accuracy)
    size = "large-v2"

    # Default to CPU if no compatible GPU detected
    if not torch.cuda.is_available():
        device = "cpu"
        print("No CUDA device detected. Running on CPU!")
        compute_type = "int8"
        size = "medium"

    # 1. Transcribe with original whisper (batched)file:///home/jason/Downloads/call-me-maybe.mp3

    model = whisperx.load_model(size, device, compute_type=compute_type, language="en")

    audio = whisperx.load_audio(speech_audio_file)
    result = model.transcribe(audio, batch_size=batch_size, language="en")

    # delete model if low on GPU resources
    # gc.collect()
    # torch.cuda.empty_cache()
    # del model

    # 2. Align whisper output
    model_a, metadata = whisperx.load_align_model(language_code="en", device=device)
    result = whisperx.align(
        result["segments"],
        model_a,
        metadata,
        audio,
        device,
        return_char_alignments=False,
    )

    with open(whisper_path, "w") as f:
        json.dump(result["segments"], f)
        print("Writing whisper transcription json to " + whisper_path)

    return whisper_path


# get_musixmatch("3TGRqZ0a2l1LRblBkJoaDx")

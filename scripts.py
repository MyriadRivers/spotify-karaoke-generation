import re
import os
import whisperx
import gc

from syrics.api import Spotify
from pytube import Search
from spleeter.separator import Separator

sp_dc = "AQCprFCayO6iKRQNux_3-4Gx8fNvLpJsRtlXzv1S9bAbzlD1plAKF4rZBsxEqX5EsqC1uHtR6nS5wTa80x6f-OfkbKgPqtegROZTERRm_KUubMqWjWinS3ilkVfO4WPMpJlLdWnjVwlijUTVM9j9-nKurM9FY9Kb"

sp = Spotify(sp_dc)

separator = Separator("spleeter:2stems")

def get_musixmatch(track_id: str):
    return sp.get_lyrics(track_id)

def download_and_split(name: str, artists: list[str], length: int, AUDIO_DIR: str, STEMS_DIR: str, MAX_TIME_DIF: int = 2) -> (str, str):
    """Downloads a song from YouTube and splits it into 2 stems. Returns path to vocals and accompaniment audio files.
    """
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

    s = Search(title)
    for video in s.results:
        # Search YouTube for first result matching search query that has a duration within max_time_dif seconds of Spotify's listed duration for the song
        if abs(video.length - length) < MAX_TIME_DIF:
            streams = video.streams.filter(only_audio=True)

            song_path = streams[0].download(AUDIO_DIR, title)

            separator.separate_to_file(song_path, STEMS_DIR)

            vocals_path = os.path.join(STEMS_DIR, title, "vocals.wav")
            accompaniment_path = os.path.join(STEMS_DIR, title, "accompaniment.wav")
            return vocals_path, accompaniment_path
        
# TODO: Change device to CPU if no gpu detected with pytorch, also change model size to fit available ram
# Put everything in a function

device = "cuda"
audio_file = "vocals.webm"
batch_size = 16 # reduce if low on GPU mem
compute_type = "float16" # change to "int8" if low on GPU mem (may reduce accuracy)

# 1. Transcribe with original whisper (batched)
model = whisperx.load_model("large-v2", device, compute_type=compute_type, language="en")

audio = whisperx.load_audio(audio_file)
result = model.transcribe(audio, batch_size=batch_size, language="en")

print(result["segments"]) # before alignment

# delete model if low on GPU resources
# import gc; gc.collect(); torch.cuda.empty_cache(); del model

# 2. Align whisper output
model_a, metadata = whisperx.load_align_model(language_code="en", device=device)
result = whisperx.align(result["segments"], model_a, metadata, audio, device, return_char_alignments=False)

print(result["segments"]) # after alignment
import os
import subprocess
import sys
import re
import json

import music_tag


NOT_LYRICS = (
    "No internet connection.",
    "No Genius API token provided.",
    "No lyrics tag. Running in offline mode.",
)

def getCurrentLine(lyrics, song_duration, song_position):
    """
    Returns the current line of lyrics based on song position.
    Uses timestamps if available, otherwise estimates based on song duration.
    
    Args:
        lyrics (str): The full lyrics text
        song_duration (float): Total duration of the song in seconds
        song_position (float): Current position in the song in seconds
        
    Returns:
        str: The current line of lyrics with any timestamps removed
    """
    if not lyrics or song_duration <= 0:
        return ''
    
    # Regex pattern to match timestamp formats like [02:48.93]
    timestamp_pattern = re.compile(r'\[(\d+):(\d+)\.(\d+)\]')
    
    # Split lyrics into lines
    lines = lyrics.split("\n")
    if not lines:
        return ''
    
    # Extract timestamps from each line if available
    timestamps = []
    for line in lines:
        timestamp_match = timestamp_pattern.search(line)
        if timestamp_match:
            minutes, seconds, milliseconds = map(int, timestamp_match.groups())
            time_in_seconds = minutes * 60 + seconds + milliseconds / 100
            timestamps.append(time_in_seconds)
        else:
            timestamps.append(None)
    
    # Check if we have valid timestamps
    has_timestamps = any(ts is not None for ts in timestamps)
    
    # Determine current line index
    current_line_idx = 0
    if has_timestamps:
        # Find the appropriate line based on current position
        for i, timestamp in enumerate(timestamps):
            if timestamp is not None and timestamp <= song_position:
                current_line_idx = i
            elif timestamp is not None and timestamp > song_position:
                break
    else:
        # Fall back to the original method if no timestamps
        current_line_idx = int((song_position * len(lines) / song_duration))
    
    # Return the current line if it's valid
    if 0 <= current_line_idx < len(lines):
        # Clean the line by removing timestamps
        return timestamp_pattern.sub('', lines[current_line_idx]).strip()
    
    return ''

        

def title_from_path(path):
    """Tries to get song artist and title from its path."""
    song_name = os.path.splitext(path)[0].strip("/").split("/")
    song_name_split = song_name[-1].split(" - ")
    if len(song_name_split) < 2:
        song_name_split = song_name[-1].split("-")
    if len(song_name_split) >= 2:
        artist = song_name_split[0]
        title = song_name_split[1]
    else:
        artist = song_name[-2]
        title = song_name[-1]
    return artist, title


def get_lyrics(song_path, offline=False, artist=None, title=None):
    """
    Tries to get song lyrics from tags then from web,
    by reading artist and title from tags,
    alternatively guessing them from song file path and name.
    """
    tags = music_tag.load_file(song_path)
    if len(str(tags["lyrics"])) > 12:
        lyrics = str(tags["lyrics"])
    else:
        lyrics = None
    if not artist:
        if tags["artist"].first:
            artist = str(tags["artist"].first)
    if not title:
        if tags["title"].first:
            title = str(tags["title"].first)
    if not artist:
        artist, _ = title_from_path(song_path)
    if not title:
        _, title = title_from_path(song_path)
    if not lyrics:
        if offline:
            lyrics = "No lyrics tag. Running in offline mode."
    return lyrics, artist, title


def cmus_status():
    """Gets song path, duration and position from cmus-remote"""
    proc = subprocess.Popen(["cmus-remote", "-Q"],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    output, error = proc.communicate()
    if error:
        print(error.decode())
        return None, None, None
    status = output.decode().split("\n")
    for line in status:
        line_split = line.split(" ")
        if line_split[0] == "file":
            song_path = line[5:]
        elif line_split[0] == "duration":
            duration = int(line_split[1:][0])
        elif line_split[0] == "position":
            position = int(line_split[1:][0])
    return song_path, duration, position


def fill_tags(song_path, lyrics, artist, title):
    """Saves lyrics, artist, and title tags, if lyrics tag is missing."""
    if lyrics not in NOT_LYRICS:
        tags = music_tag.load_file(song_path)
        if len(str(tags["lyrics"])) < 16:
            tags["lyrics"] = lyrics
            if not tags["artist"].first:
                tags["artist"] = artist
            if not tags["title"].first:
                tags["title"] = title
            tags.save()

def main():
    """Main function"""
    save_tags = False
    offline = False

    song_path, duration, position = cmus_status()
    if not song_path:
        sys.exit()
    lyrics, artist, title = get_lyrics(song_path, offline)
    if save_tags:
        fill_tags(song_path, lyrics, artist, title)
    
    current_line = getCurrentLine(lyrics, duration, position)
    output = {
        "text": current_line if current_line else "...",
        "tooltip": current_line,
        "class": "has-lyrics" if current_line else "no-lyrics"
    }
    
    print(json.dumps(output))

if __name__ == "__main__":
    main()

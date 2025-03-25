import os
import subprocess
import sys
import re
import json
import time
import signal

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
        float: Time until next line should be displayed (or None if unknown)
    """
    if not lyrics or song_duration <= 0:
        return '', None
    
    # Regex pattern to match timestamp formats like [02:48.93]
    timestamp_pattern = re.compile(r'\[(\d+):(\d+)\.(\d+)\]')
    
    # Split lyrics into lines
    lines = lyrics.split("\n")
    if not lines:
        return '', None
    
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
    time_to_next_line = None
    
    if has_timestamps:
        # Find the appropriate line based on current position
        for i, timestamp in enumerate(timestamps):
            if timestamp is not None and timestamp <= song_position:
                current_line_idx = i
            elif timestamp is not None and timestamp > song_position:
                time_to_next_line = timestamp - song_position
                break
    else:
        # Fall back to the original method if no timestamps
        current_line_idx = int((song_position * len(lines) / song_duration))
        # Estimate time to next line
        if current_line_idx < len(lines) - 1:
            time_per_line = song_duration / len(lines)
            time_to_next_line = time_per_line - (song_position % time_per_line)
    
    # Return the current line if it's valid
    if 0 <= current_line_idx < len(lines):
        # Clean the line by removing timestamps
        return timestamp_pattern.sub('', lines[current_line_idx]).strip(), time_to_next_line
    
    return '', None

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
        print(error.decode(), file=sys.stderr)
        return None, None, None
    
    song_path = None
    duration = None
    position = None
    
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

def update_waybar():
    """Update the waybar display with current lyrics"""
    song_path, duration, position = cmus_status()
    if not song_path:
        output = {
            "text": "No song playing",
            "tooltip": "No song playing",
            "class": "no-song"
        }
        print(json.dumps(output))
        return None
    
    lyrics, artist, title = get_lyrics(song_path, offline=True)
    current_line, time_to_next = getCurrentLine(lyrics, duration, position)
    
    output = {
        "text": current_line if current_line else "...",
        "tooltip": f"{artist} - {title}" if artist and title else "...",
        "class": "has-lyrics" if current_line else "no-lyrics"
    }
    
    print(json.dumps(output))
    sys.stdout.flush()
    
    return time_to_next

def main():
    """Main function"""
    # Check if we're running in continuous mode
    continuous = len(sys.argv) > 1 and sys.argv[1] == "--continuous"
    
    if continuous:
        # Handle SIGUSR1 for manual updates
        def handle_signal(signum, frame):
            update_waybar()
        
        signal.signal(signal.SIGUSR1, handle_signal)
        
        last_song = None
        
        while True:
            # Get the time until the next line should be displayed
            time_to_next = update_waybar()
            
            # If we know when the next line should appear, sleep until then
            if time_to_next is not None and time_to_next > 0:
                # Add a small offset to ensure we're ready for the next line
                sleep_time = max(0.1, time_to_next - 0.05)
                time.sleep(sleep_time)
            else:
                # Otherwise check every second
                time.sleep(1)
    else:
        # Single run mode
        update_waybar()

if __name__ == "__main__":
    main()

import argparse
import curses
import os
import signal
import subprocess
import sys
import time
import re

import music_tag

import get_lyrics_azlyrics
import get_lyrics_genius

NOT_LYRICS = (
    "No internet connection.",
    "No Genius API token provided.",
    "No lyrics tag. Running in offline mode.",
)


import curses
import re

class MinimalUI:
    """Minimal UI that displays previous, current, and next line of lyrics with centered text"""

    def __init__(self, screen):
        curses.use_default_colors()
        curses.curs_set(0)
        screen.nodelay(True)
        self.screen = screen
        self.lines = []
        self.current_line_idx = 0
        self.last_displayed_idx = -1
        # Regex pattern to match timestamp formats like [02:48.93]
        self.timestamp_pattern = re.compile(r'\[(\d+):(\d+)\.(\d+)\]')
        self.timestamps = []  # Will store timestamps in seconds for each line
        
        # Initialize colors if terminal supports them
        self._setup_colors()

    def _setup_colors(self):
        """Setup color pairs for different line types"""
        if curses.has_colors():
            curses.start_color()
            # Define color pairs: (pair_number, foreground, background)
            # Pair 1: Current line (bright white on default background)
            # LOG COLORS
            curses.init_pair(1, curses.COLOR_YELLOW, -1)
            # Pair 2: Inactive lines (dim gray on default background)
            curses.init_pair(2, curses.COLOR_WHITE, -1)
            
            # Store attributes for easy access
            self.current_line_attr = curses.color_pair(1) | curses.A_BOLD
            self.inactive_line_attr = curses.color_pair(2)
        else:
            # Fallback for terminals without color support
            self.current_line_attr = curses.A_BOLD
            self.inactive_line_attr = curses.A_DIM

    def update_lyrics(self, lyrics):
        """Loads lyrics and extracts timestamps if available"""
        self.lines = lyrics.split("\n")
        self.current_line_idx = 0
        self.last_displayed_idx = -1
        self.timestamps = []
        
        # Extract timestamps from each line if available
        for line in self.lines:
            timestamp_match = self.timestamp_pattern.search(line)
            if timestamp_match:
                minutes, seconds, milliseconds = map(int, timestamp_match.groups())
                time_in_seconds = minutes * 60 + seconds + milliseconds / 100
                self.timestamps.append(time_in_seconds)
            else:
                self.timestamps.append(None)
                
        # Check if we have valid timestamps
        self.has_timestamps = any(ts is not None for ts in self.timestamps)
        self.screen.clear()

    def scroll(self, song_duration, song_position):
        """Determines current line based on song position using timestamps if available"""
        if not self.lines or song_duration <= 0:
            return
        
        # Use timestamps if available
        if self.has_timestamps:
            # Find the appropriate line based on current position
            current_idx = 0
            for i, timestamp in enumerate(self.timestamps):
                if timestamp is not None and timestamp <= song_position:
                    current_idx = i
                elif timestamp is not None and timestamp > song_position:
                    break
            
            self.current_line_idx = current_idx
        else:
            # Fall back to the original method if no timestamps
            self.current_line_idx = int((song_position * len(self.lines) / song_duration))
        
        # Only redraw if the line has changed
        if self.current_line_idx != self.last_displayed_idx:
            self.last_displayed_idx = self.current_line_idx
            self.draw()

    def _clean_line(self, line):
        """Remove timestamp suffixes from line"""
        return self.timestamp_pattern.sub('', line).strip()

    def draw(self):
        """Draws previous, current, and next line on screen, centered horizontally"""
        h, w = self.screen.getmaxyx()
        self.screen.clear()
        
        # Center position for current line
        current_line_pos = h // 2
        prev_line_pos = current_line_pos - 2
        next_line_pos = current_line_pos + 2
        
        # Draw previous line if available
        if self.current_line_idx > 0:
            prev_line = self._clean_line(self.lines[self.current_line_idx - 1])
            self._draw_centered_line(prev_line, prev_line_pos, w, self.inactive_line_attr)
        
        # Draw current line
        if 0 <= self.current_line_idx < len(self.lines):
            current_line = self._clean_line(self.lines[self.current_line_idx])
            self._draw_centered_line(current_line, current_line_pos, w, self.current_line_attr)
            
            # Draw next line if available
            if self.current_line_idx + 1 < len(self.lines):
                next_line = self._clean_line(self.lines[self.current_line_idx + 1])
                self._draw_centered_line(next_line, next_line_pos, w, self.inactive_line_attr)
        
        self.screen.refresh()

    def _draw_centered_line(self, line, y_pos, width, attr):
        """Draw a line centered horizontally on the screen with specified attributes"""
        if not line:  # Skip empty lines
            return
            
        # If line is shorter than screen width, center it
        if len(line) < width - 2:
            x_pos = (width - len(line)) // 2
            try:
                self.screen.addstr(y_pos, x_pos, line, attr)
            except curses.error:
                # Handle potential curses errors when writing at screen boundaries
                pass
        else:
            # For longer lines, we'll need to wrap and center each part
            words = line.split()
            current_line = ""
            line_pos = y_pos
            
            for word in words:
                # Check if adding this word would exceed screen width
                if len(current_line) + len(word) + 1 < width - 2:
                    if current_line:
                        current_line += " " + word
                    else:
                        current_line = word
                else:
                    # Draw the current line centered
                    if current_line:
                        x_pos = (width - len(current_line)) // 2
                        try:
                            if line_pos < self.screen.getmaxyx()[0]:
                                self.screen.addstr(line_pos, x_pos, current_line, attr)
                        except curses.error:
                            pass
                        line_pos += 1
                    current_line = word
                    
                    # Break if we've run out of vertical space
                    if line_pos >= self.screen.getmaxyx()[0]:
                        break
            
            # Draw the last line if there's anything left
            if current_line and line_pos < self.screen.getmaxyx()[0]:
                x_pos = (width - len(current_line)) // 2
                try:
                    self.screen.addstr(line_pos, x_pos, current_line, attr)
                except curses.error:
                    pass

    def wait_input(self):
        """Handles user input for manual scrolling"""
        input_key = self.screen.getch()
        if input_key == curses.KEY_UP:
            if self.current_line_idx > 0:
                self.current_line_idx -= 1
                self.draw()
                return True
        elif input_key == curses.KEY_DOWN:
            if self.current_line_idx < len(self.lines) - 1:
                self.current_line_idx += 1
                self.draw()
                return True
        return False



class UI:
    """Methods used to draw terminal user interface"""

    def __init__(self, screen):
        curses.use_default_colors()
        curses.curs_set(0)
        screen.nodelay(True)
        self.screen = screen
        self.lines = []
        self.position = 0
        self.position_old = 0


    def update_lyrics(self, lyrics):
        """Loads lyrics"""
        self.lines = lyrics.split("\n")
        self.screen.clear()


    def scroll(self, song_duration, song_position):
        """Scrolls lyrics to position given from song duration"""
        line_index = int((song_position * len(self.lines) / song_duration))
        h, _ = self.screen.getmaxyx()
        self.position = max(0, line_index - int(h / 2))
        if self.position != self.position_old:
            self.position_old = self.position
            self.draw()


    def draw(self):
        """Draws lyrics on screen"""
        h, w = self.screen.getmaxyx()
        line_num = 0
        for line_1 in self.lines[self.position:]:
            line = line_1
            while len(line) >= w - 1:
                if line_num < h:
                    self.screen.insstr(line_num, 0, line[:w-1] + "\n")
                    line = "  " + line[w - 1:]
                    line_num += 1
                else:
                    break
            if line_num < h:
                self.screen.insstr(line_num, 0, line + "\n")
            else:
                break
            line_num += 1
        while line_num < h:
            self.screen.insstr(line_num, 0, "\n")
            line_num += 1
        self.screen.refresh()


    def wait_input(self):
        """Handles user input and window resizing"""
        h, _ = self.screen.getmaxyx()
        input_key = self.screen.getch()
        if input_key == curses.KEY_UP:
            if self.position > 0:
                self.position -= 1
                self.draw()
                return True
        elif input_key == curses.KEY_DOWN:
            h, _ = self.screen.getmaxyx()
            if self.position < len(self.lines) - h / 2:
                self.position += 1
                self.draw()
                return True
        elif input_key == curses.KEY_RESIZE:
            self.draw()
            return False
        return False



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


def get_lyrics(song_path, token, clear_headers=False, offline=False, artist=None, title=None):
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
        elif token:
            lyrics = get_lyrics_genius.download(artist, title, token, clear_headers)
        else:
            lyrics = get_lyrics_azlyrics.download(artist, title)
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


def main(screen, args):
    """Main function"""
    token = args.token
    clear_headers = args.clear_headers
    save_tags = args.save_tags
    auto_scroll = args.auto_scroll
    offline = args.offline
    minimal = args.minimal

    # Choose UI based on minimal flag
    if minimal:
        ui = MinimalUI(screen)
    else:
        ui = UI(screen)
    run = False

    song_path, duration, position = cmus_status()
    if not song_path:
        sys.exit()
    lyrics, artist, title = get_lyrics(song_path, token, clear_headers, offline)
    if save_tags:
        fill_tags(song_path, lyrics, artist, title)
    ui.update_lyrics(lyrics)
    ui.scroll(duration, position)
    ui.draw()

    song_path_old = song_path
    position_old = position

    delay = 0.05
    check_status_s = 1
    check_status = int(check_status_s / delay)
    timer = 0
    disable_auto_scroll = False
    run = True
    while run:
        if timer >= check_status:
            song_path, duration, position = cmus_status()
            timer = 0
        if song_path != song_path_old:
            if not song_path:
                break
            song_path_old = song_path
            lyrics, artist, title = get_lyrics(song_path, token, clear_headers, offline)
            ui.update_lyrics(lyrics)
            ui.draw()
            disable_auto_scroll = False
            if save_tags:
                fill_tags(song_path, lyrics, artist, title)
        if auto_scroll and not disable_auto_scroll:
            if position != position_old:
                position_old = position
                ui.scroll(duration, position)
                ui.draw()
        key_pressed = ui.wait_input()
        if key_pressed:
            disable_auto_scroll = True
        timer += 1
        time.sleep(delay)


def sigint_handler(signum, frame):   # noqa
    """Handling Ctrl-C event"""
    sys.exit()


def argparser():
    """Sets up argument parser for CLI"""
    parser = argparse.ArgumentParser(
        prog="cmus-auto-lyrics",
        description="Curses based lyrics display and fetcher for cmus music player",
    )
    parser._positionals.title = "arguments"
    parser.add_argument(
        "token",
        nargs="?",
        default=None,
        help="Genius API token - if not provided, will use azlyrics",
    )
    parser.add_argument(
        "-c",
        "--clear-headers",
        action="store_true",
        help="clear section headers in lyrics, applies only for genius",
    )
    parser.add_argument(
        "-s",
        "--save-tags",
        action="store_true",
        help="save lyrics, artist, and title tags, if lyrics tag is missing",
    )
    parser.add_argument(
        "-m",
        "--minimal",
        action="store_true",
        help="minimal mode - shows only current and next line",
    )
    parser.add_argument(
        "-a",
        "--auto-scroll",
        action="store_true",
        help="automatically scroll lyrics based on current position in song",
    )
    parser.add_argument(
        "-o",
        "--offline",
        action="store_true",
        help="runs in offline mode - only reads lyrics from tags",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version="%(prog)s 0.1.4",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = argparser()
    signal.signal(signal.SIGINT, sigint_handler)
    curses.wrapper(main, args)

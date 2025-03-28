import argparse
import curses
import os
import re
import signal
import subprocess
import sys
import time

import music_tag

import get_lyrics_azlyrics
import get_lyrics_genius

NOT_LYRICS = (
    "No internet connection.",
    "No Genius API token provided.",
    "No lyrics tag. Running in offline mode.",
)
MATCH_TIMESTAMP = re.compile(r"\[(\d{1,2}):(\d{1,2})\.(\d{1,3})\]")


class UI:
    """Methods used to draw terminal user interface"""

    def __init__(self, screen, center=False, limit_h=None, color_1=-1, color_2=3):
        curses.use_default_colors()
        curses.curs_set(0)
        screen.nodelay(True)
        self.screen = screen
        self.center = center
        self.limit_h = limit_h
        if self.limit_h is not None:
            self.limit_h += 1
        self.lines = []
        self.position = 0
        self.position_old = 0
        self.highlighted = -1
        curses.init_pair(1, color_1, -1)
        curses.init_pair(2, color_2, -1)
        self.color_normal = curses.color_pair(1)
        self.color_highlighted = curses.color_pair(2) | curses.A_BOLD


    def update_lyrics(self, lyrics):
        """Load lyrics"""
        self.lines = lyrics
        self.highlighted = -1
        self.screen.clear()


    def scroll_by_duration(self, song_duration, song_position):
        """Scroll lyrics to position given from song duration"""
        line_index = int((song_position * len(self.lines) / song_duration))
        h, _ = self.screen.getmaxyx()
        self.position = max(0, line_index - int(h / 2))
        if self.position != self.position_old:
            self.position_old = self.position
            self.draw()


    def scroll_by_index(self, line_index):
        """Scroll lyrics to specified line index"""
        h, _ = self.screen.getmaxyx()
        if self.limit_h:
            h = self.limit_h
        self.highlighted = line_index
        self.position = max(0, line_index - int(h / 2))
        if self.position != self.position_old:
            self.position_old = self.position
            self.draw()


    def draw(self):
        """Draw lyrics on screen"""
        h, w = self.screen.getmaxyx()
        line_num = 0
        if self.limit_h:
            line_num = int((h - self.limit_h) / 2)
            h = self.limit_h + line_num
        for num, line_1 in enumerate(self.lines[self.position:]):
            if num == self.highlighted - self.position:
                color = self.color_highlighted
            else:
                color = self.color_normal
            line = line_1
            while len(line) >= w - 1:
                if line_num < h:
                    newline_index = len(line[:w-1].rsplit(" ", 1)[0])
                    this_line = line[:newline_index]
                    if self.center:
                        this_line = this_line.center(w - 1)
                    self.screen.insstr(line_num, 0, this_line + "\n", color)
                    line = line[newline_index+1:]
                    line_num += 1
                else:
                    break
            if line_num < h:
                if self.center:
                    line = line.center(w - 1)
                self.screen.insstr(line_num, 0, line + "\n", color)
            else:
                break
            line_num += 1
        while line_num < h:
            self.screen.insstr(line_num, 0, "\n")
            line_num += 1
        self.screen.refresh()


    def wait_input(self):
        """Handle user input and window resizing"""
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
    """Try to get song artist and title from its path."""
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
    Try to get song lyrics from tags then from web,
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


def split_lyrics(lyrics):
    """Try to split lyrics into timestamps list and lyrics list"""
    timestamped = False
    timestamps = []
    lyrics = lyrics.split("\n")
    for num, line in enumerate(lyrics):
        timestamp = re.match(MATCH_TIMESTAMP, line)
        if timestamp:
            mins, secs, mils = map(int, timestamp.groups())
            timestamps.append(mins * 60 + secs + (mils > 50))
            timestamped = True
            lyrics[num] = line[timestamp.end():]
        else:
            timestamps.append(None)
    if timestamped:
        return lyrics, timestamps
    return lyrics, None


def find_timestamp(timestamps, position):
    """Fidnd timestamp index based on current song position"""
    for num, timestamp in enumerate(timestamps):
        if timestamp >= position:
            return num
    return 0


def cmus_status():
    """Get song path, duration and position from cmus-remote"""
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
    """Save lyrics, artist, and title tags, if lyrics tag is missing."""
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

    ui = UI(screen, args.center, args.limit_height, args.color, args.color_current)
    run = False

    song_path, duration, position = cmus_status()
    if not song_path:
        sys.exit()
    lyrics_str, artist, title = get_lyrics(song_path, token, clear_headers, offline)
    lyrics, timestamps = split_lyrics(lyrics_str)
    if save_tags:
        fill_tags(song_path, lyrics_str, artist, title)
    ui.update_lyrics(lyrics)
    if timestamps:
        ui.scroll_by_index(find_timestamp(timestamps, position))
    else:
        ui.scroll_by_duration(duration, position)
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
            lyrics_str, artist, title = get_lyrics(song_path, token, clear_headers, offline)
            lyrics, timestamps = split_lyrics(lyrics_str)
            ui.update_lyrics(lyrics)
            ui.draw()
            disable_auto_scroll = False
            if save_tags:
                fill_tags(song_path, lyrics_str, artist, title)
        if auto_scroll and not disable_auto_scroll:
            if position != position_old:
                position_old = position
                if timestamps:
                    ui.scroll_by_index(find_timestamp(timestamps, position))
                else:
                    ui.scroll_by_duration(duration, position)
                ui.draw()
        key_pressed = ui.wait_input()
        if key_pressed:
            disable_auto_scroll = True
        timer += 1
        time.sleep(delay)


def sigint_handler(signum, frame):   # noqa
    """Handle Ctrl-C event"""
    sys.exit()


def argparser():
    """Setup argument parser for CLI"""
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
        "-e",
        "--center",
        action="store_true",
        help="center lyrics",
    )
    parser.add_argument(
        "-l",
        "--limit_height",
        type=int,
        help="limit number of lyrics lines visivble on screen, will center lyrics vertically",
    )
    parser.add_argument(
        "--color",
        type=int,
        default=-1,
        help="8bit ANSI color code for all lyrics lines",
    )
    parser.add_argument(
        "--color_current",
        type=int,
        default=3,
        help="8bit ANSI color code for current lyrics line (when timestamps are available)",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version="%(prog)s 0.2.2",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = argparser()
    signal.signal(signal.SIGINT, sigint_handler)
    curses.wrapper(main, args)

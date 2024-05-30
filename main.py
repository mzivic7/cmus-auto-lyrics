import music_tag
import curses
import subprocess
import argparse
import signal
import time
import sys


import get_lyrics_genius
import get_lyrics_azlyrics


class UI:
    def __init__(self, screen):
        curses.use_default_colors()
        curses.curs_set(0)
        screen.nodelay(True)
        self.screen = screen
        self.lines = []
        self.line_index = 0
        self.line_index_old = 0


    def update_lyrics(self, lyrics):
        """Loads lyrics"""
        self.lines = lyrics.split("\n")
        self.screen.clear()


    def scroll(self, duration, position):
        """Scrolls lyrics to position given from song duration"""
        self.line_index = int((position * len(self.lines) / duration))
        if self.line_index_old != self.line_index:
            self.line_index_old = self.line_index
            self.position = position
            self.duration = duration
            self.draw()
        h, _ = self.screen.getmaxyx()
        self.position = max(0, self.line_index - int(h / 2))


    def draw(self):
        """Draws lyrics on screen"""
        h, w = self.screen.getmaxyx()
        line_num = 0
        for line in self.lines[self.position:]:
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
    song_name = path.rstrip(".m4a").rstrip(".mp3").split("/")
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
    """Tries to get song lyrics from tags then from web,
    by reading artist and title from tags,
    alternatively guessing them from song file path and name."""
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
        else:
            if token:
                lyrics = get_lyrics_genius.download(artist, title, token, clear_headers)
            else:
                lyrics = get_lyrics_azlyrics.download(artist, title)
    return lyrics, artist, title


def cmus_status():
    """Gets song path, duration and position from cmus-remote"""
    proc = subprocess.Popen(['cmus-remote', '-Q'],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    output, error = proc.communicate()
    status = output.decode().split('\n')
    for line in status:
        line_split = line.split(" ")
        if line_split[0] == 'file':
            song_path = line[5:]
        elif line_split[0] == 'duration':
            duration = int(line_split[1:][0])
        elif line_split[0] == 'position':
            position = int(line_split[1:][0])
    if error:
        return None, None, None
    return song_path, duration, position


def fill_tags(song_path, lyrics, artist, title):
    """Saves lyrics, artist, and title tags, if lyrics tag is missing."""
    tags = music_tag.load_file(song_path)
    if len(str(tags["lyrics"])) < 16:
        tags["lyrics"] = lyrics
        if not tags["artist"].first:
            tags["artist"] = artist
        if not tags["title"].first:
            tags["title"] = title


def main(screen, args):
    token = args.token
    clear_headers = args.clear_headers
    save_tags = args.save_tags
    auto_scroll = args.auto_scroll
    offline = args.offline

    ui = UI(screen)
    run = False

    song_path, duration, position = cmus_status()
    if not song_path:
        sys.exit()
    lyrics, artist, title = get_lyrics(song_path, token, clear_headers, offline)
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
                if lyrics not in ("No internet connection.",
                                  "No Genius API token provided.",
                                  "No lyrics tag. Running in offline mode."):
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
        time.sleep(0.05)


def sigint_handler(signum, frame):
    sys.exit()


def argparser():
    """Sets up argument parser for CLI"""
    parser = argparse.ArgumentParser(
        prog="cmus-auto-lyrics",
        description="Curses based lyrics display and fetcher for cmus music player"
        )
    parser._positionals.title = "arguments"
    parser.add_argument(
        "token",
        nargs="?",
        default=None,
        help="Genius API token - if not provided, will use azlyrics"
        )
    parser.add_argument(
        "-c",
        "--clear-headers",
        action="store_true",
        help="clear section headers in lyrics, applies only for genius"
        )
    parser.add_argument(
        "-s",
        "--save-tags",
        action="store_true",
        help="save lyrics, artist, and title tags, if lyrics tag is missing"
        )
    parser.add_argument(
        "-a",
        "--auto-scroll",
        action="store_true",
        help="automatically scroll lyrics based on current position in song"
        )
    parser.add_argument(
        "-o",
        "--offline",
        action="store_true",
        help="runs in offline mode - only reads lyrics from tags"
        )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version="%(prog)s 0.1.0"
        )
    return parser.parse_args()


if __name__ == "__main__":
    args = argparser()
    signal.signal(signal.SIGINT, sigint_handler)
    curses.wrapper(main, args)

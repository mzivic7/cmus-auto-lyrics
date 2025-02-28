import lyricsgenius
from requests.exceptions import ConnectionError as requests_ConnectionError

# https://github.com/johnwmillr/LyricsGenius

blacklist = ["Contributors"]


def download(artist, title, token, clear_headers=False):
    """Download lyrics from genius, clear them and optionally remove headers (eg. [bridge])"""
    # setup genius
    if not token:
        return "No Genius API token provided."
    genius = lyricsgenius.Genius(token)
    genius.remove_section_headers = clear_headers
    genius.excluded_terms = ["(Remix)", "instrumental"]
    genius.skip_non_songs = True
    genius.verbose = False

    # download lyrics
    genius_title = ""
    try:
        song = genius.search_song(title, artist)
        try:
            lyrics = song.lyrics
            genius_title = song.title
        except Exception:
            return "Lyrics not found."
    except requests_ConnectionError:
        return "No internet connection."

    # clean lyrics
    lyrics = lyrics.replace(genius_title + " Lyrics", "")
    lyrics = lyrics.replace("Embed", "")
    lyrics = lyrics.replace("Share URLCopyCopy", "")
    lyrics = lyrics.replace("You might also like", "")
    str_numbers = list(map(str, range(10)))

    # remove numbers
    for n in range(3):
        if lyrics[-1] in str_numbers:
            lyrics = lyrics[:-1]

    # remove double newline
    lyrics = lyrics.replace("\n\n", "\n")

    # remove lines containing blacklisted words
    lyrics_split = lyrics.split("\n")
    lyrics_new = ""
    not_lyrics = False
    for line in lyrics_split:
        if len(line) > 500:
            not_lyrics = True
            break
        if any([x not in line for x in blacklist]):
            lyrics_new += line + "\n"
    lyrics = lyrics_new

    # remove lyrics with single line longer than 500 characters
    # its probably not lyrics
    if not_lyrics:
        return "Lyrics not found."

    # remove leading newlines
    while lyrics[:1] == "\n":
        lyrics = lyrics[1:]
    return lyrics


if __name__ == "__main__":
    import sys
    artist = sys.argv[1].replace("%20", " ")
    title = sys.argv[2].replace("%20", " ")
    token = sys.argv[3].replace("%20", " ")
    lyrics = download(artist, title, token)
    print(lyrics)

import lyricsgenius
from requests.exceptions import ConnectionError
# https://github.com/johnwmillr/LyricsGenius

blacklist = ["Contributors"]


def download(artist, title, token, clear_headers=False):
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
    except ConnectionError:
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

    # remove lines containing blacklisted words
    lyrics_split = lyrics.split("\n")
    lyrics_new = ""
    for line in lyrics_split:
        if any([x not in line for x in blacklist]):
            lyrics_new += line + "\n"
    lyrics = lyrics_new

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

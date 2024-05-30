from azlyrics.azlyrics import lyrics as lyrics_getter
from requests.exceptions import ConnectionError
# https://github.com/adhorrig/azlyrics


def download(artist, title):
    # download lyrics
    try:
        lyrics = lyrics_getter(artist, title)[0]
    except ConnectionError:
        return "No internet connection."
    except Exception:
        return "Lyrics not found."

    # remove leading newlines
    while lyrics[:1] in ("\n"):
        lyrics = lyrics[1:]
    return lyrics


if __name__ == "__main__":
    import sys
    artist = sys.argv[1].replace("%20", " ")
    title = sys.argv[2].replace("%20", " ")
    lyrics = download(artist, title)
    print(lyrics)

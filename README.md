# cmus-auto-lyrics
Curses based lyrics display and fetcher for [cmus](https://cmus.github.io) music player with auto scroll and tag support.

## Features
- Runs as daemon and connects to cmus-remote  
- Reads lyrics from tags if available  
- Tries to guess song artist and title from file name and path  
- Downloads lyrics from Genius (API token required)  
- Downloads lyrics from azlyrics if Genius API token is not provided  
- Automatically scrolls lyrics based on current position in song  
- Saves lyrics, artist and title to tags (optional)  
- Removes section headers from Genius lyrics (optional)  
- Manual scroll deactivates auto scroll for current song  
- Offline mode - forces only reading from tags  

## Usage
```
usage: cmus-auto-lyrics [-h] [-c] [-s] [-a] [-o] [-v] [token]

Curses based lyrics display and fetcher for cmus music player

arguments:
  token                Genius API token - if not provided, will use azlyrics

options:
  -h, --help           show this help message and exit
  -c, --clear-headers  clear section headers in lyrics
  -s, --save-tags      save lyrics, artist, and title tags, if lyrics tag is missing
  -a, --auto-scroll    automatically scroll lyrics based on current position in song
  -o, --offline        runs in offline mode, only reads lyrics from tags
  -v, --version        show program's version number and exit

```

### How to help it guess artist and title from path
If there are no tags, keep file names as follows:  
`<artist> - <title>.<extension>`  
`<artist>-<title>.<extension>`  
or file name is just song name and parent directory is artist:  
`<artist>/<title>.<extension>`  

## Installing
- From AUR: yay -S cmus-auto-lyrics
- Build, then copy built executable to system:  
`sudo cp dist/cmus-rpc-py /usr/local/sbin/`

## Building
1. Clone this repository: `git clone https://github.com/mzivic7/cmus-auto-lyrics`
2. Install [pipenv](https://docs.pipenv.org/install/)
3. `cd cmus-auto-lyrics`
4. Install requirements: `pipenv install`
5. build: `pipenv run python -m PyInstaller --noconfirm --onefile --windowed --clean --name "cmus-auto-lyrics" "main.py"`

## Launcher
Example launcher for cmus with cmus-auto-lyrics in single terminal with tmux, with enabled auto-scroll.  
Launching in open terminal:  
```
bash -c "tmux new-session -s cmus -d -x '$(tput cols)' -y '$(tput lines)' $'cmus'; tmux split -h -l40 $'cmus-auto-lyrics -a'; tmux select-pane -t 0; tmux attach -t cmus"
```
Launching with maximized gnome terminal (can be added as launcher):  
```
gnome-terminal --window --maximize -- /bin/sh -c "tmux new-session -s cmus -d -x '$(tput cols)' -y '$(tput lines)' $'cmus'; tmux split -h -l40 $'cmus-auto-lyrics -a'; tmux select-pane -t 0; tmux attach -t cmus"
```
Launching with [cmus-rpc-py](https://github.com/mzivic7/cmus-rpc-py):
```
bash -c "tmux new-session -s cmus -d -x '$(tput cols)' -y '$(tput lines)' $'cmus-rpc-py -s & cmus'; tmux split -h -l40 $'cmus-auto-lyrics -a'; tmux select-pane -t 0; tmux attach -t cmus"
```
Note: change `-l40` to number of columns that should be used by lyrics pane.  

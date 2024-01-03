# plex-watchlist-dvr
Plex Watchlist DVR

This script will schedule DVR recordings for movies in your Plex Watchlist.

Note: The `requests` pip package will need to be  installed for this work work

## Using the script
Change plex_baseurl and plex_token based on your local installation of Plex.
If your movies section is not called Movies, change the following line as appropriate:
```
watchlist = dvr.watchlist_to_recordings("Movies")
```

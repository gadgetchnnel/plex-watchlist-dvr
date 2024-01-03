import json
from plexapi.server import PlexServer
from datetime import datetime

plex_baseurl = '<your plex server url here>'
plex_token = '<your plex token>'


def find_in_dvr_schedule(subscriptions, item):
    sub_type = "1" if item.type == "movie" else "2"
    return next((s for s in subscriptions if s.type == sub_type
                 and s.item.title.lower() == item.title.lower()
                 and s.item.year == item.year), None)


def in_library(library_movies, item):
    library_match = next((m for m in library_movies if m.guid == item.guid), None)
    duration_percent = ((library_match.duration / item.duration) * 100) if library_match else 0
    return duration_percent > 50


class PlexDVRTest(movie_section):
    def __init__(self, baseurl, token):
        self._token = token
        self._plex = PlexServer(baseurl, token)

    def watchlist_to_recordings(self):
        watchlist = []
        account = self._plex.myPlexAccount()
        watchlist_movies = account.watchlist(libtype="movie")
        library_movies_section = self._plex.library.section(movie_section)
        library_movies = library_movies_section.search(libtype="movie")
        subs = self._plex.dvr.subscriptions()
        dvr_movies_section = self._plex.dvr.section("Movies")
        for movie in watchlist_movies:
            item = {
                "title": movie.title, 
                "year": movie.year, 
                "in_library": False,
                "recording_scheduled": False,
                "recording_schedule_created": None,
                "newly_scheduled": False
            }
            if in_library(library_movies, movie):
                item["in_library"] = True
                watchlist.append(item)
                continue
            scheduled_recording = find_in_dvr_schedule(subs, movie)
            if scheduled_recording:
                item["recording_scheduled"] = True
                item["recording_schedule_created"] = scheduled_recording.createdAt.isoformat()
                watchlist.append(item)
                continue
            dvr_matches = dvr_movies_section.search(libtype="movie", title=movie.title, year=movie.year)
            # Filter matches to ensure only exact title matches are returned
            dvr_matches = [match for match in dvr_matches if movie.title in match.title == movie.title]
            if dvr_matches:
                dvr_match = dvr_matches[0]
                self._plex.dvr.submitRecording(dvr_match, movie.thumb)
                item["recording_scheduled"] = True
                item["newly_scheduled"] = True
                item["recording_schedule_created"] = datetime.now().isoformat()
            watchlist.append(item)
        return {"watchlist": watchlist}


dvr = PlexDVRTest(plex_baseurl, plex_token)
watchlist = dvr.watchlist_to_recordings("Movies")
print(json.dumps(watchlist, ensure_ascii=False, indent=4))

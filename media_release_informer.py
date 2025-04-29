#!/usr/bin/env python3
import requests
import json
import datetime
import os
import sys
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = Path('.') / '.env'
load_dotenv(dotenv_path=env_path)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("release_notifier")


# Configuration
class Config:
    # Discord webhook URL
    DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")

    # Radarr configurations
    RADARR_INSTANCES = [
        {
            "name": "Movies 4K",
            "url": os.environ.get("RADARR_4K_URL", ""),
            "api_key": os.environ.get("RADARR_4K_API_KEY", ""),
        },
        {
            "name": "Movies",
            "url": os.environ.get("RADARR_URL", ""),
            "api_key": os.environ.get("RADARR_API_KEY", ""),
        }
    ]

    # Sonarr configurations
    SONARR_INSTANCES = [
        {
            "name": "Anime",
            "url": os.environ.get("SONARR_ANIME_URL", ""),
            "api_key": os.environ.get("SONARR_ANIME_API_KEY", ""),
        },
        {
            "name": "TV Shows",
            "url": os.environ.get("SONARR_URL", ""),
            "api_key": os.environ.get("SONARR_API_KEY", ""),
        }
    ]


class RadarrAPI:
    def __init__(self, base_url: str, api_key: str, instance_name: str):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.instance_name = instance_name
        self.headers = {
            "X-Api-Key": self.api_key,
            "Content-Type": "application/json"
        }

    def get_movies(self) -> List[Dict[str, Any]]:
        """Get all monitored movies from Radarr"""
        try:
            response = requests.get(f"{self.base_url}/api/v3/movie", headers=self.headers)
            response.raise_for_status()
            all_movies = response.json()
            return [movie for movie in all_movies if movie.get('monitored', False)]
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching movies from {self.instance_name}: {e}")
            return []

    def get_todays_releases(self) -> List[Dict[str, Any]]:
        """Get all movies being released today"""
        today = datetime.datetime.now().strftime('%Y-%m-%d')
        movies = self.get_movies()
        return [
            movie for movie in movies
            if movie.get('digitalRelease') and movie.get('digitalRelease', '').startswith(today)
               or movie.get('physicalRelease') and movie.get('physicalRelease', '').startswith(today)
               or movie.get('inCinemas') and movie.get('inCinemas', '').startswith(today)
        ]


class SonarrAPI:
    def __init__(self, base_url: str, api_key: str, instance_name: str):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.instance_name = instance_name
        self.headers = {
            "X-Api-Key": self.api_key,
            "Content-Type": "application/json"
        }

    def get_series(self) -> List[Dict[str, Any]]:
        """Get all monitored series from Sonarr"""
        try:
            response = requests.get(f"{self.base_url}/api/v3/series", headers=self.headers)
            response.raise_for_status()
            all_series = response.json()
            return [series for series in all_series if series.get('monitored', False)]
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching series from {self.instance_name}: {e}")
            return []

    def get_calendar(self, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """Get calendar items between start_date and end_date"""
        try:
            params = {
                "start": start_date,
                "end": end_date,
                "includeEpisodeFile": "true",  # Include file info if available
                "includeEpisodeImages": "false",  # No need for images
                "includeSeriesImages": "false"  # No need for images
            }
            response = requests.get(f"{self.base_url}/api/v3/calendar", headers=self.headers, params=params)
            response.raise_for_status()
            calendar_items = response.json()

            # Enrich calendar items with series information
            for item in calendar_items:
                if 'seriesId' in item and not ('series' in item and 'title' in item.get('series', {})):
                    try:
                        series_response = requests.get(
                            f"{self.base_url}/api/v3/series/{item['seriesId']}",
                            headers=self.headers
                        )
                        if series_response.status_code == 200:
                            item['series'] = series_response.json()
                    except requests.exceptions.RequestException:
                        pass  # If we can't get series info, just continue

            return calendar_items
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching calendar from {self.instance_name}: {e}")
            return []

    def get_todays_episodes(self) -> List[Dict[str, Any]]:
        """Get all episodes airing today"""
        today = datetime.datetime.now().strftime('%Y-%m-%d')
        tomorrow = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime('%Y-%m-%d')
        return self.get_calendar(today, tomorrow)


class DiscordNotifier:
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def send_notification(self, movie_releases: Dict[str, List[Dict[str, Any]]],
                          tv_releases: Dict[str, List[Dict[str, Any]]]) -> bool:
        """Send a notification to Discord with today's releases"""
        today = datetime.datetime.now().strftime('%Y-%m-%d')

        # Build the message content
        message = f"# Media Releases for {today}\n\n"

        # Add movie releases to the message
        has_movies = False
        for instance, movies in movie_releases.items():
            if movies:
                if not has_movies:
                    message += "## Movies\n\n"
                    has_movies = True
                message += f"### {instance}\n"
                for movie in movies:
                    title = movie.get('title', 'Unknown Title')
                    year = movie.get('year', 'Unknown Year')

                    # Determine the release type
                    release_type = ""
                    if movie.get('digitalRelease', '').startswith(today):
                        release_type = "Digital Release"
                    elif movie.get('physicalRelease', '').startswith(today):
                        release_type = "Physical Release"
                    elif movie.get('inCinemas', '').startswith(today):
                        release_type = "In Cinemas"

                    tmdb_id = movie.get('tmdbId', '')
                    tmdb_link = f"https://www.themoviedb.org/movie/{tmdb_id}" if tmdb_id else ""

                    message += f"- **{title}** ({year}) - {release_type}"
                    if tmdb_link:
                        message += f" - [TMDB]({tmdb_link})"
                    message += "\n"
                message += "\n"

        # Add TV episodes to the message
        has_episodes = False
        for instance, episodes in tv_releases.items():
            if episodes:
                if not has_episodes:
                    message += "## TV Episodes\n\n"
                    has_episodes = True
                message += f"### {instance}\n"

                # Let's add debug logging to see the structure
                if episodes and len(episodes) > 0:
                    logger.debug(f"Sample episode structure: {json.dumps(episodes[0], indent=2)}")

                # Group episodes by series
                series_episodes = {}
                for episode in episodes:
                    # Use a consistent approach - first try to get series info from the parent object
                    if 'series' in episode and isinstance(episode['series'], dict):
                        series_title = episode['series'].get('title', 'Unknown Series')
                    # Then try other fields
                    elif 'seriesTitle' in episode:
                        series_title = episode.get('seriesTitle', 'Unknown Series')
                    else:
                        series_title = 'Unknown Series'
                        logger.warning(f"Could not find series title for episode: {episode}")

                    if series_title not in series_episodes:
                        series_episodes[series_title] = []
                    series_episodes[series_title].append(episode)

                # Add episodes for each series
                for series_title, series_eps in series_episodes.items():
                    # Get TVDB ID if available
                    tvdb_id = ''
                    if 'series' in series_eps[0] and isinstance(series_eps[0]['series'], dict):
                        tvdb_id = series_eps[0]['series'].get('tvdbId', '')

                    tvdb_link = f"https://thetvdb.com/series/{tvdb_id}" if tvdb_id else ""

                    message += f"- **{series_title}**"
                    if tvdb_link:
                        message += f" - [TVDB]({tvdb_link})"
                    message += "\n"

                    for episode in series_eps:
                        # Get season and episode numbers
                        season_num = episode.get('seasonNumber', 0)
                        episode_num = episode.get('episodeNumber', 0)

                        # Get episode title - most commonly in 'title' field
                        episode_title = episode.get('title', 'Unknown Episode')

                        # Get air date
                        air_date = episode.get('airDate', 'Unknown Date')
                        if not air_date and 'airDateUtc' in episode:
                            air_date_utc = episode.get('airDateUtc')
                            try:
                                # Try to parse ISO format date
                                date_obj = datetime.datetime.fromisoformat(air_date_utc.replace('Z', '+00:00'))
                                air_date = date_obj.strftime('%Y-%m-%d')
                            except (ValueError, AttributeError):
                                air_date = 'Unknown Date'

                        message += f"  - S{season_num:02d}E{episode_num:02d} - {episode_title} ({air_date})\n"
                message += "\n"

        # Check if there are no releases today
        if not has_movies and not has_episodes:
            message += "No monitored content is being released today.\n"

        # Send the message to Discord
        payload = {
            "content": message
        }

        try:
            response = requests.post(self.webhook_url, json=payload)
            response.raise_for_status()
            logger.info(f"Notification sent successfully!")
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Error sending notification: {e}")
            return False


def main():
    # logging.getLogger().setLevel(logging.DEBUG)
    logger.info("Starting media release notifier...")

    # Validate configuration
    if not Config.DISCORD_WEBHOOK_URL:
        logger.error("Discord webhook URL is not configured!")
        return

    # Initialize Discord notifier
    discord = DiscordNotifier(Config.DISCORD_WEBHOOK_URL)

    # Get movie releases from Radarr instances
    movie_releases = {}
    for instance in Config.RADARR_INSTANCES:
        if instance["url"] and instance["api_key"]:
            radarr = RadarrAPI(instance["url"], instance["api_key"], instance["name"])
            releases = radarr.get_todays_releases()
            movie_releases[instance["name"]] = releases
            logger.info(f"Found {len(releases)} movie releases for {instance['name']}")

    # Get TV episodes from Sonarr instances
    tv_releases = {}
    for instance in Config.SONARR_INSTANCES:
        if instance["url"] and instance["api_key"]:
            sonarr = SonarrAPI(instance["url"], instance["api_key"], instance["name"])
            episodes = sonarr.get_todays_episodes()
            tv_releases[instance["name"]] = episodes
            logger.info(f"Found {len(episodes)} episode releases for {instance['name']}")

    # Send notification
    success = discord.send_notification(movie_releases, tv_releases)
    if success:
        logger.info("Daily media release notification completed successfully!")
    else:
        logger.error("Failed to send release notification.")


if __name__ == "__main__":
    main()
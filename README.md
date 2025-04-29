# Media Release Notifier

A Python application that sends daily Discord notifications about movies and TV shows being released today, based on your monitored content in Radarr and Sonarr.

## Features

- Checks multiple Radarr and Sonarr instances for releases (I use 4 total, but you can use as many or as little as you'd like)
- Supports separate instances for different content types (4K movies, regular movies, anime, TV shows)
- Sends formatted Discord messages with release information
- Includes links to TMDB for movies and TVDB for TV shows
- Groups TV episodes by series for better readability

## Requirements

- Python 3.6+
- `requests` library
- Radarr and Sonarr instances with API access
- Discord webhook URL

## Setup

1. Install the required Python package:
   ```
   pip install requests
   ```

2. Configure your environment variables by copying the `config.env` file to `.env`:
   ```
   cp config.env .env
   ```

3. Edit the `.env` file with your actual configuration values:
   - Add your Discord webhook URL
   - Add URLs and API keys for your Radarr and Sonarr instances

## Usage

### Running manually

```
python release_notifier.py
```

### Setting up a daily cron job

To run the script automatically every morning, add a cron job:

1. Open your crontab for editing:
   ```
   crontab -e
   ```

2. Add a line to run the script at 8:00 AM every day (adjust the path to match your setup):
   ```
   0 8 * * * cd /path/to/media-release-notifier && python release_notifier.py
   ```

### Running with Docker

1. Create a Dockerfile:
   ```
   FROM python:3.9-slim
   
   WORKDIR /app
   
   COPY requirements.txt .
   RUN pip install --no-cache-dir -r requirements.txt
   
   COPY release_notifier.py .
   
   CMD ["python", "release_notifier.py"]
   ```

2. Create a requirements.txt file:
   ```
   requests==2.31.0
   python-dotenv==1.0.0
   ```

3. Build and run the Docker container:
   ```
   docker build -t media-release-notifier .
   docker run --env-file .env media-release-notifier
   ```

## Discord Message Format

The notification will include:

- Date of releases
- Movies section (if any releases today)
  - Grouped by Radarr instance
  - Movie title, year, and release type (digital, physical, or cinema)
  - TMDB links
- TV Shows section (if any episodes today)
  - Grouped by Sonarr instance and then by series
  - Series title with TVDB link
  - Episode details (season number, episode number, title, air date)

## Troubleshooting

- Check that your API keys have proper permissions
- Verify that your Radarr/Sonarr URLs are correct and include the port number
- Ensure your Discord webhook URL is valid
- Check the logs for any error messages

## Extending

- To add more Radarr or Sonarr instances, update the configuration in the `Config` class
- You can customize the message format in the `send_notification` method of the `DiscordNotifier` class

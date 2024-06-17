# Telegram RSS Feed Bot

This bot allows users to manage RSS feeds and receive updates via Telegram. Users can add, list, and delete RSS feeds. The bot periodically checks for updates and sends new entries to users' chat or a specified channel.

## Features

- **Add RSS Feeds:** Users can add RSS feed URLs to receive updates.
- **List RSS Feeds:** Users can list their added RSS feeds.
- **Delete RSS Feeds:** Users can remove RSS feed URLs from their list.
- **Automatic Updates:** The bot checks RSS feeds for updates every 5 minutes and sends new entries to the user.
- **Manual Feed Check:** Users can manually trigger the feed check process.

## Commands

- `/start`: Register the bot and set the channel for RSS updates if the command is issued in a group or channel.
- `/add <RSS_feed_url>`: Add an RSS feed URL to receive updates (_for example /add https://www.reddit.com/r/europe.rss_)
- `/list`: List all added RSS feeds.
- `/delete <RSS_feed_url>`: Delete a specified RSS feed URL.
- `/check`: Manually trigger an RSS feed check for updates.

## To-Do List

- Add functionality to work within channels.
- Integrate database strucure instead of .json

## Setup Instructions

1. Clone the repository.
2. Create a `.env` file with your Telegram bot token:

    ```
    TELEGRAM_BOT_TOKEN=your_telegram_bot_token
    ```

3. Install the required dependencies:

    ```bash
    pip install -r requirements.txt
    ```

4. Run the bot:

    ```bash
    python main.py
    ```

## Dependencies

- `aiohttp`
- `feedparser`
- `python-telegram-bot`
- `python-dotenv`
- `schedule`

## Logging

The bot uses Python's logging module to log important information and errors. Logs are printed to the console with timestamps.

## JSON Files

- `user_feeds.json`: Stores user RSS feeds.
- `posted_entries.json`: Tracks posted entries to avoid duplicates.

Feel free to contribute to this project by opening issues or submitting pull requests!

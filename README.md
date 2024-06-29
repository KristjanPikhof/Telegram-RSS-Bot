# Telegram RSS Feed Bot

This bot allows users to manage RSS feeds and receive updates via Telegram. Users can add, list, and delete RSS feeds. The bot periodically checks for updates and sends new entries to users' chat or a specified channel.

## Features

- **Add RSS Feeds:** Users can add RSS feed URLs to receive updates (including YouTube channels).
- **List RSS Feeds:** Users can list their added RSS feeds.
- **Delete RSS Feeds:** Users can remove RSS feed URLs from their list.
- **Automatic Updates:** The bot checks RSS feeds for updates at customizable intervals.
- **Customizable Update Interval:** Users can set their preferred update frequency.
- **Manual Feed Check:** Users can manually trigger the feed check process.

## Commands

- `/start`: Register the bot and set the channel for RSS updates if the command is issued in a group or channel.
- `/add <RSS_feed_url>`: Add an RSS feed URL to receive updates (for example `/add https://reddit.com/r/europe.rss` or `/add https://youtube.com/@IntoEurope`)
- `/list`: List all added RSS feeds.
- `/delete <RSS_feed_url>`: Delete a specified RSS feed URL.
- `/check`: Manually trigger an RSS feed check for updates.
- `/update <minutes>`: Set the update interval for RSS feed checks.

## To-Do List

- Add functionality to work within channels.
- Integrate database structure instead of `.json`.

## Setup Instructions

1. Clone the repository:

    ```bash
    git clone https://github.com/KristjanPikhof/Telegram-RSS-Bot.git
    ```

2. Fill the `.env` file with your information:

    ```
    TELEGRAM_BOT_TOKEN=your_telegram_bot_token
    YOUTUBE_API_KEY=your_google_console_api_key
    ```

3. Install the required dependencies:

    ```bash
    pip install -r requirements.txt
    ```

4. Run the bot:

    ```bash
    python main.py
    ```

### [How to get YouTube API key 🔑?](https://developers.google.com/youtube/v3/getting-started)
### [How to create Telegram Bot and get the bot token?](https://core.telegram.org/bots/tutorial)

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
- `user_settings.json`: Stores user-specific settings like update intervals.

Feel free to contribute to this project by opening issues or submitting pull requests!
import logging
import os
import asyncio
import aiohttp
import feedparser
import schedule
import json
from datetime import datetime
from dotenv import load_dotenv
from pathlib import Path
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackContext, JobQueue

# Load environment variables from .env file
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL_CONFIG_FILE = 'channel_config.json'

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("No TELEGRAM_BOT_TOKEN found in environment variables")

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s: %(message)s',
                    datefmt='%d.%m.%Y %H:%M:%S')
logger = logging.getLogger(__name__)

FEEDS_FILE = 'user_feeds.json'
POSTED_ENTRIES_FILE = 'posted_entries.json'

def load_json(file_path):
    """Load JSON data from a file"""
    file_path = Path(file_path)
    if file_path.exists():
        with file_path.open('r') as file:
            return json.load(file)
    return {}

def save_json(data, file_path):
    """Save JSON data to a file"""
    file_path = Path(file_path)
    with file_path.open('w') as file:
        json.dump(data, file)
    logger.info(f'Saved data to {file_path}')

def load_data():
    """Load user feeds and posted entries from JSON files"""
    user_feeds = load_json(FEEDS_FILE)
    posted_entries = load_json(POSTED_ENTRIES_FILE)
    channel_id = load_json(CHANNEL_CONFIG_FILE).get('channel_id')
    return user_feeds, posted_entries, channel_id

def save_data(user_feeds, posted_entries, channel_id):
    """Save user feeds, posted entries, and channel ID to JSON files"""
    save_json(user_feeds, FEEDS_FILE)
    save_json(posted_entries, POSTED_ENTRIES_FILE)

    # Check if channel_id is a string or an integer
    if isinstance(channel_id, int):
        channel_id = str(channel_id)

    save_json({'channel_id': channel_id}, CHANNEL_CONFIG_FILE)
    logger.info(f'Saved data to {FEEDS_FILE}, {POSTED_ENTRIES_FILE}, and {CHANNEL_CONFIG_FILE}')

async def validate_feed_url(feed_url):
    """Validate the RSS feed URL"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(feed_url, timeout=10) as response:
                return response.status == 200, 'Feed URL is valid.' if response.status == 200 else 'Feed URL is not reachable. Please check the URL and try again.'
    except Exception as e:
        return False, f'Error: {str(e)}'

async def fetch_feed(session, feed_url):
    """Fetch and parse the RSS feed"""
    try:
        async with session.get(feed_url, timeout=10) as response:
            if response.status == 200:
                feed_data = await response.text()
                return feedparser.parse(feed_data), None
            else:
                return None, f'Error fetching {feed_url}: HTTP {response.status}'
    except Exception as e:
        return None, f'Error fetching {feed_url}: {str(e)}'

async def check_feeds(context: ContextTypes.DEFAULT_TYPE, user_feeds, posted_entries, channel_id, bot):
    """Check RSS feeds for updates"""
    logger.info('Checking feeds...')
    current_time = datetime.utcnow().isoformat()

    async with aiohttp.ClientSession() as session:
        tasks = [fetch_feed(session, feed_url) for user_id, feeds in user_feeds.items() for feed_url in feeds]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for (feed, error), (user_id, feed_url) in zip(results, [(u, f) for u, feeds in user_feeds.items() for f in feeds]):
            if error:
                logger.error(error)
                continue

            for entry in feed.entries:
                entry_id = entry.get('id', entry.link)
                if user_id not in posted_entries:
                    posted_entries[user_id] = {}
                if entry_id not in posted_entries[user_id]:
                    message_text = f'⚡️ [{entry.title}]({entry.link})'
                    if channel_id and str(user_id) == channel_id:
                        await bot.send_message(chat_id=user_id, text=message_text, parse_mode='Markdown')
                    else:
                        await bot.send_message(chat_id=user_id, text=message_text, parse_mode='Markdown')
                    posted_entries[user_id][entry_id] = current_time

    if channel_id:
        await post_to_channel(context, user_feeds, posted_entries, channel_id)

    save_data(user_feeds, posted_entries, channel_id)
    logger.info('Feed check completed')

async def post_to_channel(context: CallbackContext, user_feeds, posted_entries, channel_id):
    """Post updates to the channel"""
    current_time = datetime.utcnow().isoformat()

    async with aiohttp.ClientSession() as session:
        tasks = [fetch_feed(session, feed_url) for user_id, feeds in user_feeds.items() for feed_url in feeds]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for feed, error in results:
            if error:
                logger.error(error)
                continue

            for entry in feed.entries:
                entry_id = entry.get('id', entry.link)
                if entry_id not in posted_entries.get(channel_id, {}):
                    message_text = f'⚡️ [{entry.title}]({entry.link})'
                    await context.bot.send_message(chat_id=channel_id, text=message_text, parse_mode='Markdown')
                    if channel_id not in posted_entries:
                        posted_entries[channel_id] = {}
                    posted_entries[channel_id][entry_id] = current_time

async def run_scheduler():
    """Run scheduled tasks"""
    while True:
        schedule.run_pending()
        await asyncio.sleep(1)

async def main():
    """Start the bot"""
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    job_queue: JobQueue = application.job_queue  # Get the JobQueue instance

    # Load initial data
    user_feeds, posted_entries, channel_id = load_data()

    # Register command handlers
    from commands import start, add_feed, list_feeds, delete_feed, manual_check
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("add", add_feed))
    application.add_handler(CommandHandler("list", list_feeds))
    application.add_handler(CommandHandler("delete", delete_feed))
    application.add_handler(CommandHandler("check", lambda update, context: manual_check(update, context, check_feeds, application)))

    # Initialize bot data
    application.bot_data = {
        'user_feeds': user_feeds,
        'posted_entries': posted_entries,
        'channel_id': channel_id
    }

    # Start the bot and scheduler
    logger.info("Bot started. Listening for commands...")

    # Schedule the check_feeds function to run every 5 minutes
    job_queue.run_repeating(lambda context: check_feeds(context, user_feeds, posted_entries, channel_id, application.bot), interval=300)

    await application.initialize()
    await application.start()
    await application.updater.start_polling()

    # Keep the event loop running indefinitely
    loop = asyncio.get_running_loop()
    try:
        await asyncio.Future()  # Run forever
    finally:
        await application.stop()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except RuntimeError as e:
        if 'This event loop is already running' in str(e):
            loop = asyncio.get_running_loop()
            loop.create_task(main())
            loop.run_forever()
        else:
            raise
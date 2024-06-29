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
USER_SETTINGS_FILE = 'user_settings.json'

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
    """Load user feeds, posted entries, channel ID, and user settings from JSON files"""
    user_feeds = load_json(FEEDS_FILE)
    posted_entries = load_json(POSTED_ENTRIES_FILE)
    channel_id = load_json(CHANNEL_CONFIG_FILE).get('channel_id')
    user_settings = load_json(USER_SETTINGS_FILE)
    return user_feeds, posted_entries, channel_id, user_settings

def save_data(user_feeds, posted_entries, channel_id, user_settings):
    """Save user feeds, posted entries, channel ID, and user settings to JSON files"""
    save_json(user_feeds, FEEDS_FILE)
    save_json(posted_entries, POSTED_ENTRIES_FILE)
    save_json({'channel_id': channel_id}, CHANNEL_CONFIG_FILE)
    save_json(user_settings, USER_SETTINGS_FILE)
    logger.info(f'Saved data to {FEEDS_FILE}, {POSTED_ENTRIES_FILE}, {CHANNEL_CONFIG_FILE}, and {USER_SETTINGS_FILE}')

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
        for user_id, feeds in user_feeds.items():
            for feed_url in feeds:
                feed, error = await fetch_feed(session, feed_url)
                if error:
                    logger.error(error)
                    continue

                for entry in feed.entries:
                    entry_id = entry.get('id', entry.link)
                    if user_id not in posted_entries:
                        posted_entries[user_id] = {}
                    if entry_id not in posted_entries[user_id]:
                        message_text = f'⚡️ [{entry.title}]({entry.link})'
                        await bot.send_message(chat_id=user_id, text=message_text, parse_mode='Markdown')
                        posted_entries[user_id][entry_id] = current_time

    if channel_id:
            await post_to_channel(context, user_feeds, posted_entries, channel_id)

    # Get user_settings from context.bot_data
    user_settings = context.bot_data.get('user_settings', {})
    
    save_data(user_feeds, posted_entries, channel_id, user_settings)
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

def format_timedelta(td):
    """Format a timedelta object into a human-readable string"""
    total_seconds = int(td.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    parts = []
    if hours > 0:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    if minutes > 0:
        parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
    if seconds > 0:
        parts.append(f"{seconds} second{'s' if seconds != 1 else ''}")
    
    return ", ".join(parts) if parts else "less than a second"

def update_job_interval(context: CallbackContext, chat_id: str, interval: int):
    """Update the job interval for a specific chat and return the new job"""
    job_name = f"feed_check_{chat_id}"
    current_jobs = context.job_queue.get_jobs_by_name(job_name)
    
    for job in current_jobs:
        job.schedule_removal()
    
    async def callback(context: CallbackContext):
        await check_feeds(context, {chat_id: context.bot_data['user_feeds'].get(chat_id, [])}, 
                          {chat_id: context.bot_data['posted_entries'].get(chat_id, {})}, 
                          context.bot_data['channel_id'], context.bot)

    new_job = context.job_queue.run_repeating(
        callback,
        interval=interval * 60,
        first=0,
        name=job_name
    )
    
    return new_job

async def run_scheduler():
    """Run scheduled tasks"""
    while True:
        schedule.run_pending()
        await asyncio.sleep(1)

async def main():
    """Start the bot"""
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    job_queue: JobQueue = application.job_queue

    # Load initial data
    user_feeds, posted_entries, channel_id, user_settings = load_data()

    # Initialize bot data
    application.bot_data = {
        'user_feeds': user_feeds,
        'posted_entries': posted_entries,
        'channel_id': channel_id,
        'user_settings': user_settings
    }

    # Register command handlers
    from commands import start, add_feed, list_feeds, delete_feed, manual_check, update_every
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("add", add_feed))
    application.add_handler(CommandHandler("list", list_feeds))
    application.add_handler(CommandHandler("delete", delete_feed))
    application.add_handler(CommandHandler("check", lambda update, context: manual_check(update, context, check_feeds, application)))
    application.add_handler(CommandHandler("update", update_every))

    # Start the bot and scheduler
    logger.info("Bot started. Listening for commands...")

    # Schedule the check_feeds function for each user/chat
    for chat_id, feeds in user_feeds.items():
        settings = user_settings.get(chat_id, {})
        interval = settings.get('update_interval', 30) # Default update interval 30min
        job_queue.run_repeating(
            lambda context, chat=chat_id: check_feeds(context, {chat: feeds}, 
                                                      {chat: posted_entries.get(chat, {})}, 
                                                      channel_id, application.bot),
            interval=interval * 60,
            name=f"feed_check_{chat_id}"
        )

    await application.initialize()
    await application.start()
    await application.updater.start_polling()

    # Keep the event loop running
    loop = asyncio.get_running_loop()
    try:
        await asyncio.Future()
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
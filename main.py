import logging
import os
import asyncio
import aiohttp
import feedparser
import schedule
import json
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from dotenv import load_dotenv
from youtube import convert_to_rss_feed

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

# Global dictionary to store user_id and their RSS feeds
user_feeds = {}
posted_entries = {}  # Dictionary to keep track of posted entries
channel_id = None  # Variable to store channel ID

FEEDS_FILE = 'user_feeds.json'
POSTED_ENTRIES_FILE = 'posted_entries.json'

def load_json(file_path):
    """Load JSON data from a file"""
    if os.path.exists(file_path):
        with open(file_path, 'r') as file:
            return json.load(file)
    return {}

def save_json(data, file_path):
    """Save JSON data to a file"""
    with open(file_path, 'w') as file:
        json.dump(data, file)
    logger.info(f'Saved data to {file_path}')

def load_feeds():
    """Load user feeds from a JSON file"""
    global user_feeds
    user_feeds = load_json(FEEDS_FILE)
    logger.info('Loaded user feeds from JSON file.')

def save_feeds():
    """Save user feeds to a JSON file"""
    save_json(user_feeds, FEEDS_FILE)
    logger.info('Saved user feeds to JSON file.')

def load_posted_entries():
    """Load posted entries from a JSON file"""
    global posted_entries
    posted_entries = load_json(POSTED_ENTRIES_FILE)
    logger.info('Loaded posted entries from JSON file.')

def save_posted_entries():
    """Save posted entries to a JSON file"""
    save_json(posted_entries, POSTED_ENTRIES_FILE)
    logger.info('Saved posted entries to JSON file.')

def load_channel_id():
    """Load channel ID from a JSON file"""
    global channel_id
    config = load_json(CHANNEL_CONFIG_FILE)
    channel_id = config.get('channel_id')
    logger.info('Loaded channel ID from config file.')

def save_channel_id():
    """Save channel ID to a JSON file"""
    global channel_id
    save_json({'channel_id': channel_id}, CHANNEL_CONFIG_FILE)
    logger.info('Saved channel ID to config file.')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Respond to the /start command"""
    logger.info(f'Received /start from {update.message.from_user.id}')
    if update.message.chat.type in ['group', 'supergroup', 'channel']:
        global channel_id
        channel_id = update.message.chat.id
        save_channel_id()
        await update.message.reply_text("📢 This channel is now set for RSS feed updates.")
        logger.info(f'Set channel ID to {channel_id}')
    else:
        welcome_message = (
            "👋 **Welcome!**\n\n"
            "Use the following commands to manage your RSS feeds:\n\n"
            "📥 **Add a feed:** `/add <RSS_feed_url>`\n"
            "📜 **List your feeds:** `/list`\n"
            "🗑️ **Remove a feed:** `/delete <RSS_feed_url>`"
        )
        await update.message.reply_text(welcome_message, parse_mode='Markdown')

async def add_feed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Add an RSS feed for the user"""
    user_id = str(update.message.from_user.id)
    feed_url = ' '.join(context.args)
    if not feed_url:
        await update.message.reply_text('📥 Please provide an RSS feed URL after the /add command.')
        return
    
    # Support for YouTube RSS
    if 'youtube.com' in feed_url:
        try:
            feed_url = await convert_to_rss_feed(feed_url)
        except ValueError as e:
            await update.message.reply_text(str(e))
            return
    else:
        # Validate the feed URL for non-YouTube feeds
        valid, message = await validate_feed_url(feed_url)
        if not valid:
            await update.message.reply_text(message)
            return

    if user_id in user_feeds:
        user_feeds[user_id].append(feed_url)
    else:
        user_feeds[user_id] = [feed_url]
    save_feeds()  # Save feeds to JSON after adding
    logger.info(f'Added feed for user {user_id}: {feed_url}')
    await update.message.reply_text(f'📜 Added feed: {feed_url}')

async def list_feeds(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List all RSS feeds for the user"""
    user_id = str(update.message.from_user.id)
    if user_id in user_feeds and user_feeds[user_id]:
        feeds = "\n".join(user_feeds[user_id])
        await update.message.reply_text(f'📜 Your feeds:\n{feeds}')
    else:
        await update.message.reply_text('📜 You have no feeds added.')

async def delete_feed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Delete an RSS feed for the user"""
    user_id = str(update.message.from_user.id)
    feed_url = ' '.join(context.args)
    if user_id in user_feeds and feed_url in user_feeds[user_id]:
        user_feeds[user_id].remove(feed_url)
        if not user_feeds[user_id]:  # Remove the user entry if no feeds left
            del user_feeds[user_id]
        save_feeds()  # Save feeds to JSON after deleting
        logger.info(f'Deleted feed for user {user_id}: {feed_url}')
        await update.message.reply_text(f'🗑️ Deleted feed: {feed_url}')
    else:
        await update.message.reply_text('❌ Feed not found.')

async def validate_feed_url(feed_url):
    """Validate the RSS feed URL"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(feed_url, timeout=10) as response:
                if response.status == 200:
                    return True, 'Feed URL is valid.'
                else:
                    return False, 'Feed URL is not reachable. Please check the URL and try again.'
    except Exception as e:
        return False, f'Error: {str(e)}'

async def fetch_feed(session, user_id, feed_url):
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

async def check_feeds():
    """Check RSS feeds for updates"""
    logger.info('Checking feeds...')
    current_time = datetime.utcnow().isoformat()  # Get the current time in ISO format

    async with aiohttp.ClientSession() as session:
        tasks = []
        for user_id, feeds in user_feeds.items():
            for feed_url in feeds:
                tasks.append(fetch_feed(session, user_id, feed_url))
        
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
                    await bot.send_message(chat_id=user_id, text=message_text, parse_mode='Markdown')
                    posted_entries[user_id][entry_id] = current_time  # Track posted entry with timestamp

    # Post to the channel if configured
    if channel_id:
        await post_to_channel(session)

    save_posted_entries()  # Save posted entries after checking feeds
    logger.info('Feed check completed')

async def post_to_channel(session):
    """Post updates to the channel"""
    tasks = []
    for user_id, feeds in user_feeds.items():
        for feed_url in feeds:
            tasks.append(fetch_feed(session, user_id, feed_url))
    
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for (feed, error) in results:
        if error:
            logger.error(error)
            continue

        for entry in feed.entries:
            entry_id = entry.get('id', entry.link)
            if entry_id not in posted_entries.get(channel_id, {}):
                message_text = f'⚡️ [{entry.title}]({entry.link})'
                await bot.send_message(chat_id=channel_id, text=message_text, parse_mode='Markdown')
                if channel_id not in posted_entries:
                    posted_entries[channel_id] = {}
                posted_entries[channel_id][entry_id] = datetime.utcnow().isoformat()  # Track posted entry with timestamp

async def run_scheduler():
    """Run scheduled tasks"""
    while True:
        schedule.run_pending()
        await asyncio.sleep(1)

# Add a new handler for manually triggering the feed check
async def manual_check(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Manual trigger to check RSS feeds"""
    logger.info(f'Received /check from {update.message.from_user.id}')
    await check_feeds()
    await update.message.reply_text('✅ Manual feed check completed.')

async def main():
    global bot
    """Start the bot"""
    load_feeds()  # Load feeds from JSON file at startup
    load_posted_entries()  # Load posted entries from JSON file at startup
    load_channel_id()  # Load channel ID from JSON file at startup
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    bot = application.bot

    # Register command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("add", add_feed))
    application.add_handler(CommandHandler("list", list_feeds))
    application.add_handler(CommandHandler("delete", delete_feed))
    application.add_handler(CommandHandler("check", manual_check))

    # Start the bot and scheduler
    logger.info("Bot started. Listening for commands...")
    schedule.every(5).minutes.do(lambda: asyncio.create_task(check_feeds()))

    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    
    # Run scheduler concurrently with the bot
    await run_scheduler()

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

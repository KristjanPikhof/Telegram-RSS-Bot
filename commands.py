import logging
from telegram import Update
from telegram.ext import ContextTypes
from youtube import convert_to_rss_feed
from main import save_data

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s: %(message)s',
                    datefmt='%d.%m.%Y %H:%M:%S')
logger = logging.getLogger(__name__)

async def start(update: Update, callback_data: ContextTypes.DEFAULT_TYPE) -> None:
    """Respond to the /start command"""
    chat_type = update.effective_chat.type
    chat_id = str(update.effective_chat.id)
    logger.info(f'Received /start from {chat_id} ({chat_type})')

    if chat_type in ['group', 'supergroup', 'channel']:
        user_feeds = callback_data.bot_data['user_feeds']
        posted_entries = callback_data.bot_data['posted_entries']
        channel_id = callback_data.bot_data['channel_id']

        if chat_id not in user_feeds:
            user_feeds[chat_id] = []
            callback_data.bot_data['user_feeds'] = user_feeds
            logger.info(f'Added new chat ID {chat_id} to user_feeds')

        if channel_id and channel_id != chat_id:
            logger.warning(f'Channel ID {channel_id} already set, but received /start from {chat_id}')

        callback_data.bot_data['channel_id'] = chat_id
        await update.effective_message.reply_text("📢 This chat is now set for RSS feed updates.")
        logger.info(f'Set channel ID to {chat_id}')

        # Save the updated data
        save_data(user_feeds, posted_entries, chat_id)
    else:
        welcome_message = (
            "👋 **Welcome!**\n\n"
            "Use the following commands to manage your RSS feeds:\n\n"
            "📥 **Add a feed:** `/add <RSS_feed_url>`\n"
            "📜 **List your feeds:** `/list`\n"
            "🗑️ **Remove a feed:** `/delete <RSS_feed_url>`\n"
            "✅ **Check feeds manually:** `/check`"
        )
        await update.effective_message.reply_text(welcome_message, parse_mode='Markdown')

async def add_feed(update: Update, callback_data: ContextTypes.DEFAULT_TYPE) -> None:
    """Add an RSS feed for the user or channel"""
    chat_id = str(update.effective_chat.id)
    feed_url = ' '.join(callback_data.args)
    if not feed_url:
        await update.effective_message.reply_text('📥 Please provide an RSS feed URL after the /add command.')
        return

    # Support for YouTube RSS
    if 'youtube.com' in feed_url:
        try:
            feed_url = await convert_to_rss_feed(feed_url)
        except ValueError as e:
            await update.effective_message.reply_text(str(e))
            return

    user_feeds, posted_entries, channel_id = callback_data.bot_data['user_feeds'], callback_data.bot_data['posted_entries'], callback_data.bot_data['channel_id']

    if chat_id not in user_feeds:
        user_feeds[chat_id] = []

    if feed_url not in user_feeds[chat_id]:
        user_feeds[chat_id].append(feed_url)
        callback_data.bot_data['user_feeds'] = user_feeds
        logger.info(f'Added feed for chat {chat_id}: {feed_url}')
        await update.effective_message.reply_text(f'📜 Added feed: {feed_url}')

        # Save the updated data
        save_data(user_feeds, posted_entries, channel_id)
    else:
        await update.effective_message.reply_text('❌ Feed already added.')

async def list_feeds(update: Update, callback_data: ContextTypes.DEFAULT_TYPE) -> None:
    """List all RSS feeds for the user or channel"""
    chat_id = str(update.effective_chat.id)
    user_feeds = callback_data.bot_data['user_feeds']

    if chat_id in user_feeds and user_feeds[chat_id]:
        feeds = "\n".join(user_feeds[chat_id])
        await update.effective_message.reply_text(f'📜 Feeds for this chat:\n{feeds}')
    else:
        await update.effective_message.reply_text('📜 No feeds added for this chat.')

async def delete_feed(update: Update, callback_data: ContextTypes.DEFAULT_TYPE) -> None:
    """Delete an RSS feed for the user or channel"""
    chat_id = str(update.effective_chat.id)
    feed_url = ' '.join(callback_data.args)
    user_feeds = callback_data.bot_data['user_feeds']
    posted_entries = callback_data.bot_data['posted_entries']
    channel_id = callback_data.bot_data['channel_id']

    if chat_id in user_feeds and feed_url in user_feeds[chat_id]:
        user_feeds[chat_id].remove(feed_url)
        if not user_feeds[chat_id]:  # Remove the chat entry if no feeds left
            del user_feeds[chat_id]
        callback_data.bot_data['user_feeds'] = user_feeds
        logger.info(f'Deleted feed for chat {chat_id}: {feed_url}')
        await update.effective_message.reply_text(f'🗑️ Deleted feed: {feed_url}')

        # Save the updated data
        save_data(user_feeds, posted_entries, channel_id)
    else:
        await update.effective_message.reply_text('❌ Feed not found for this chat.')

async def manual_check(update: Update, context: ContextTypes.DEFAULT_TYPE, check_feeds_func, application) -> None:
    """Manual trigger to check RSS feeds"""
    logger.info(f'Received /check from {update.effective_chat.id}')
    chat_id = str(update.effective_chat.id)
    user_feeds = context.bot_data['user_feeds']
    posted_entries = context.bot_data['posted_entries']
    channel_id = context.bot_data['channel_id']
    await check_feeds_func(context, user_feeds, posted_entries, channel_id, application.bot)
    await update.effective_message.reply_text('✅ Manual feed check completed.')
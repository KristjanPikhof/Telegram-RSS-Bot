import logging
import re
import os
import requests
from dotenv import load_dotenv

load_dotenv()
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def extract_rss_feed_url(youtube_url):
    # Extract the channel name from the URL
    channel_name = youtube_url.split('@')[-1]
    
    # Fetch Channel ID using YouTube Data API v3
    search_url = "https://youtube.googleapis.com/youtube/v3/search"
    params = {
        "part": "snippet",
        "q": channel_name,
        "type": "channel",
        "key": YOUTUBE_API_KEY
    }
    response = requests.get(search_url, params=params)
    
    if response.status_code != 200:
        raise Exception(f"Failed to fetch channel ID: {response.status_code} - {response.text}")
    
    data = response.json()
    if not data.get("items"):
        raise Exception("Channel not found")
    
    channel_id = data["items"][0]["snippet"]["channelId"]
    
    # Construct RSS Feed URL
    rss_feed_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    
    return rss_feed_url

async def convert_to_rss_feed(youtube_url):
    """
    Converts a YouTube channel URL to its corresponding RSS feed URL.
    
    Args:
    youtube_url (str): The YouTube channel URL.
    
    Returns:
    str: The RSS feed URL.
    """
    # Normalizing the URL
    if not youtube_url.startswith('https://'):
        youtube_url = 'https://' + youtube_url
    youtube_url = youtube_url.replace('www.', '')
    
    # Check if the URL is already a full RSS feed URL
    if 'youtube.com/feeds/videos.xml' in youtube_url:
        return youtube_url
    
    # Check if the URL contains a channel ID
    channel_id_match = re.search(r'channel/([\w-]+)', youtube_url)
    if channel_id_match:
        channel_id = channel_id_match.group(1)
        return f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    
    # Check if the URL is in the format https://www.youtube.com/@ChannelName
    if re.match(r'https://youtube\.com/@[\w-]+', youtube_url):
        return await extract_rss_feed_url(youtube_url)
    
    raise ValueError("Invalid YouTube channel URL format.")
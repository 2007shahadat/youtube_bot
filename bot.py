import os
import logging
import asyncio
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes
)
from googleapiclient.discovery import build

# Load environment variables
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

# YouTube API setup
youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)

# Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Subscribed channels {chat_id: [channel_ids]}
subscribed_channels = {}

# Last video cache {channel_id: latest_video_id}
last_videos = {}

# ----------------- Command Handlers -----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎬 *Full YouTube Bot* 🎬\n\n"
        "Commands:\n"
        "/search <keyword> - Search videos\n"
        "/channel <channel_id> - Subscribe to channel updates\n"
        "/trending - Show trending videos\n"
        "/playlist <playlist_id> - Fetch playlist videos\n"
        "/videoinfo <video_url> - Get video info",
        parse_mode="Markdown"
    )

async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args)
    if not query:
        await update.message.reply_text("Please provide search keyword: /search funny cats")
        return
    res = youtube.search().list(part="snippet", q=query, type="video", maxResults=5).execute()
    items = res.get("items", [])
    if not items:
        await update.message.reply_text("No videos found.")
        return
    for item in items:
        title = item['snippet']['title']
        video_id = item['id']['videoId']
        thumbnail = item['snippet']['thumbnails']['high']['url']
        url = f"https://www.youtube.com/watch?v={video_id}"
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Watch on YouTube", url=url)]])
        await update.message.reply_photo(photo=thumbnail, caption=title, reply_markup=keyboard)

async def channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in subscribed_channels:
        subscribed_channels[chat_id] = []
    if not context.args:
        await update.message.reply_text("Please provide Channel ID: /channel UC_x5XG1OV2P6uZZ5FSM9Ttw")
        return
    channel_id = context.args[0]
    if channel_id in subscribed_channels[chat_id]:
        await update.message.reply_text("Already subscribed!")
    else:
        subscribed_channels[chat_id].append(channel_id)
        await update.message.reply_text(f"Subscribed to channel: {channel_id}")

async def trending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    res = youtube.videos().list(part="snippet", chart="mostPopular", maxResults=5, regionCode="US").execute()
    for item in res.get("items", []):
        title = item['snippet']['title']
        video_id = item['id']
        thumbnail = item['snippet']['thumbnails']['high']['url']
        url = f"https://www.youtube.com/watch?v={video_id}"
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Watch", url=url)]])
        await update.message.reply_photo(photo=thumbnail, caption=title, reply_markup=keyboard)

async def playlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Please provide playlist ID: /playlist PLxxxx")
        return
    playlist_id = context.args[0]
    res = youtube.playlistItems().list(part="snippet", playlistId=playlist_id, maxResults=5).execute()
    for item in res.get("items", []):
        title = item['snippet']['title']
        video_id = item['snippet']['resourceId']['videoId']
        url = f"https://www.youtube.com/watch?v={video_id}"
        thumbnail = item['snippet']['thumbnails']['high']['url']
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Watch", url=url)]])
        await update.message.reply_photo(photo=thumbnail, caption=title, reply_markup=keyboard)

async def videoinfo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Please provide video URL: /videoinfo https://www.youtube.com/watch?v=xxxx")
        return
    url = context.args[0]
    video_id = url.split("v=")[-1]
    res = youtube.videos().list(part="snippet,statistics", id=video_id).execute()
    item = res['items'][0]
    title = item['snippet']['title']
    desc = item['snippet']['description']
    views = item['statistics'].get('viewCount', 'N/A')
    likes = item['statistics'].get('likeCount', 'N/A')
    publish = item['snippet']['publishedAt']
    msg = f"🎥 {title}\n\nViews: {views}\nLikes: {likes}\nPublished: {publish}\n\nDescription:\n{desc}"
    await update.message.reply_text(msg)

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(text=f"You clicked: {query.data}")

# ----------------- Background Task -----------------
async def check_new_videos(app: Application):
    await asyncio.sleep(5)  # wait for bot to start
    while True:
        for chat_id, channels in subscribed_channels.items():
            for channel_id in channels:
                try:
                    res = youtube.channels().list(part="contentDetails", id=channel_id).execute()
                    uploads_id = res['items'][0]['contentDetails']['relatedPlaylists']['uploads']
                    playlist_res = youtube.playlistItems().list(part="snippet", playlistId=uploads_id, maxResults=1).execute()
                    video_id = playlist_res['items'][0]['snippet']['resourceId']['videoId']
                    if channel_id not in last_videos:
                        last_videos[channel_id] = video_id
                    elif last_videos[channel_id] != video_id:
                        last_videos[channel_id] = video_id
                        url = f"https://www.youtube.com/watch?v={video_id}"
                        title = playlist_res['items'][0]['snippet']['title']
                        await app.bot.send_message(chat_id, f"📢 New video from {channel_id}:\n{title}\n{url}")
                except Exception as e:
                    logger.error(f"Error checking channel {channel_id}: {e}")
        await asyncio.sleep(60)

# ----------------- Main -----------------
async def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    # Add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("search", search))
    app.add_handler(CommandHandler("channel", channel))
    app.add_handler(CommandHandler("trending", trending))
    app.add_handler(CommandHandler("playlist", playlist))
    app.add_handler(CommandHandler("videoinfo", videoinfo))
    app.add_handler(CallbackQueryHandler(button))

    # Start background task AFTER bot starts
    asyncio.create_task(check_new_videos(app))

    print("Bot is running...")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())

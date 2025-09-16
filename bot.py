import os
import logging
import asyncio
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from googleapiclient.discovery import build

# Load environment variables
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

# YouTube API
youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)

# Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Subscriptions
subscribed_channels = {}
last_videos = {}

# ----------------- Handlers -----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎬 *Full YouTube Bot* 🎬\n\n"
        "Commands:\n"
        "/search <keyword>\n"
        "/channel <channel_id>\n"
        "/trending\n"
        "/playlist <playlist_id>\n"
        "/videoinfo <video_url>",
        parse_mode="Markdown"
    )

async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args)
    if not query:
        await update.message.reply_text("Use: /search funny cats")
        return
    res = youtube.search().list(part="snippet", q=query, type="video", maxResults=5).execute()
    for item in res.get("items", []):
        title = item['snippet']['title']
        video_id = item['id']['videoId']
        url = f"https://www.youtube.com/watch?v={video_id}"
        thumbnail = item['snippet']['thumbnails']['high']['url']
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Watch", url=url)]])
        await update.message.reply_photo(photo=thumbnail, caption=title, reply_markup=keyboard)

async def channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in subscribed_channels:
        subscribed_channels[chat_id] = []
    if not context.args:
        await update.message.reply_text("Use: /channel UC_x5XG1OV2P6uZZ5FSM9Ttw")
        return
    channel_id = context.args[0]
    if channel_id not in subscribed_channels[chat_id]:
        subscribed_channels[chat_id].append(channel_id)
        await update.message.reply_text(f"Subscribed to channel: {channel_id}")
    else:
        await update.message.reply_text("Already subscribed!")

async def trending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    res = youtube.videos().list(part="snippet", chart="mostPopular", maxResults=5, regionCode="US").execute()
    for item in res.get("items", []):
        title = item['snippet']['title']
        video_id = item['id']
        url = f"https://www.youtube.com/watch?v={video_id}"
        thumbnail = item['snippet']['thumbnails']['high']['url']
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Watch", url=url)]])
        await update.message.reply_photo(photo=thumbnail, caption=title, reply_markup=keyboard)

async def playlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Use: /playlist PLxxxx")
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
        await update.message.reply_text("Use: /videoinfo <video_url>")
        return
    video_id = context.args[0].split("v=")[-1]
    res = youtube.videos().list(part="snippet,statistics", id=video_id).execute()
    item = res['items'][0]
    msg = f"🎥 {item['snippet']['title']}\nViews: {item['statistics'].get('viewCount','N/A')}\nLikes: {item['statistics'].get('likeCount','N/A')}\nPublished: {item['snippet']['publishedAt']}\n\n{item['snippet']['description']}"
    await update.message.reply_text(msg)

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(text=f"You clicked: {query.data}")

# ----------------- Background -----------------
async def check_new_videos(app: Application):
    await asyncio.sleep(5)
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
    # Build Application WITHOUT JobQueue
    app = Application.builder().token(TELEGRAM_TOKEN).post_init(None).build()

    # Add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("search", search))
    app.add_handler(CommandHandler("channel", channel))
    app.add_handler(CommandHandler("trending", trending))
    app.add_handler(CommandHandler("playlist", playlist))
    app.add_handler(CommandHandler("videoinfo", videoinfo))
    app.add_handler(CallbackQueryHandler(button))

    # Start background task
    asyncio.create_task(check_new_videos(app))

    print("Bot is running...")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())

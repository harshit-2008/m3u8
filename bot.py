import logging
import os
import asyncio
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackContext, MessageHandler, filters

# Configure logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Scheduler for scheduling future recordings
scheduler = BackgroundScheduler()
scheduler.start()

# Global variables
current_recording = None
current_recording_start_time = None
recordings = []
recordings_dir = 'recordings'
os.makedirs(recordings_dir, exist_ok=True)

# Add your bot token here
TOKEN = '7439562089:AAERgxvEYiLJF_juL68k1nn78negwJ3mNiM'

# Command handlers
async def start(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text(
        "Welcome to the M3U8 Recording Bot!\n"
        "Available commands:\n"
        "/start - Start the bot\n"
        "/help - Show this help message\n"
        "/record <M3U8 link> [<duration>] [<format>] [<resolution>] [<quality>] - Start recording the M3U8 stream\n"
        "/status - Show the current status of the bot\n"
        "/cancel - Cancel the current operation\n"
        "/timing - Show the start time of the recording\n"
        "/history - Show the download history\n"
        "/schedule <time> <M3U8 link> [<duration>] [<format>] [<resolution>] [<quality>] - Schedule a recording"
    )

async def help_command(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text(
        "Here are the available commands:\n"
        "/start - Start the bot\n"
        "/help - Show this help message\n"
        "/record <M3U8 link> [<duration>] [<format>] [<resolution>] [<quality>] - Start recording the M3U8 stream\n"
        "/status - Show the current status of the bot\n"
        "/cancel - Cancel the current operation\n"
        "/timing - Show the start time of the recording\n"
        "/history - Show the download history\n"
        "/schedule <time> <M3U8 link> [<duration>] [<format>] [<resolution>] [<quality>] - Schedule a recording"
    )

async def record(update: Update, context: CallbackContext) -> None:
    global current_recording, current_recording_start_time
    
    if current_recording is not None:
        await update.message.reply_text("A recording is already in progress. Please stop it before starting a new one.")
        return
    
    if len(context.args) < 1:
        await update.message.reply_text("Please provide the M3U8 link.")
        return

    m3u8_link = context.args[0]
    duration = context.args[1] if len(context.args) > 1 else None
    format_ = context.args[2] if len(context.args) > 2 else 'mkv'
    resolution = context.args[3] if len(context.args) > 3 else None
    quality = context.args[4] if len(context.args) > 4 else None
    
    filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_recording.{format_}"
    filepath = os.path.join(recordings_dir, filename)

    # Start the recording (simulated by just waiting for 5 seconds)
    current_recording = context.args
    current_recording_start_time = datetime.now()
    await update.message.reply_text(f"Started recording: {m3u8_link}.\nDuration: {duration}, Format: {format_}, Resolution: {resolution}, Quality: {quality}")

    # Simulate recording
    await asyncio.sleep(5)  # Replace this with actual recording logic
    current_recording = None
    recordings.append(filename)

    await update.message.reply_text(f"Recording saved as {filename}")

async def status(update: Update, context: CallbackContext) -> None:
    if current_recording:
        await update.message.reply_text(f"Recording in progress: {current_recording[0]}\nDuration: {current_recording[1] if len(current_recording) > 1 else 'N/A'}")
    else:
        await update.message.reply_text("No recording in progress.")

async def cancel(update: Update, context: CallbackContext) -> None:
    global current_recording
    if current_recording:
        # Cancel the ongoing recording (if there was actual recording logic, it should be stopped here)
        current_recording = None
        await update.message.reply_text("Recording has been cancelled.")
    else:
        await update.message.reply_text("No recording to cancel.")

async def timing(update: Update, context: CallbackContext) -> None:
    if current_recording_start_time:
        start_time_str = current_recording_start_time.strftime('%Y-%m-%d %H:%M:%S')
        await update.message.reply_text(f"Recording started at {start_time_str}.")
    else:
        await update.message.reply_text("No recording in progress.")

async def history(update: Update, context: CallbackContext) -> None:
    if recordings:
        history_list = "\n".join(recordings)
        await update.message.reply_text(f"Download history:\n{history_list}")
    else:
        await update.message.reply_text("No recordings in the history.")

async def schedule(update: Update, context: CallbackContext) -> None:
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /schedule <time> <M3U8 link> [<duration>] [<format>] [<resolution>] [<quality>]")
        return

    schedule_time_str = context.args[0]
    m3u8_link = context.args[1]
    duration = context.args[2] if len(context.args) > 2 else None
    format_ = context.args[3] if len(context.args) > 3 else 'mkv'
    resolution = context.args[4] if len(context.args) > 4 else None
    quality = context.args[5] if len(context.args) > 5 else None
    
    schedule_time = datetime.strptime(schedule_time_str, '%Y-%m-%d %H:%M:%S')
    delay = (schedule_time - datetime.now()).total_seconds()

    if delay < 0:
        await update.message.reply_text("Scheduled time is in the past. Please specify a future time.")
        return

    scheduler.add_job(
        lambda: asyncio.run(record(update, context)),  # Schedule the recording
        'date',
        run_date=schedule_time,
        id=f'schedule_{schedule_time_str}',  # Unique ID for this job
        replace_existing=True  # Replace any existing job with the same ID
    )

    await update.message.reply_text(f"Recording scheduled for {schedule_time_str}.")

async def main() -> None:
    # Create the Application and pass it your bot's token.
    application = Application.builder().token(TOKEN).build()

    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("record", record))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("cancel", cancel))
    application.add_handler(CommandHandler("timing", timing))
    application.add_handler(CommandHandler("history", history))
    application.add_handler(CommandHandler("schedule", schedule))

    # Add a handler for non-command messages
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: None))

    # Run the bot
    await application.run_polling()

if __name__ == '__main__':
    asyncio.run(main())
                 

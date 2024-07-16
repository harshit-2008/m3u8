

# Define the bot token (Replace with your actual token)
TOKEN = ''

# Define the chat ID for file uploads (Replace with your actual chat ID)
CHAT_ID = ''

import os
import logging
import subprocess
import signal
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackContext, CallbackQueryHandler

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define the path for recordings
RECORDINGS_DIR = 'recordings'
if not os.path.exists(RECORDINGS_DIR):
    os.makedirs(RECORDINGS_DIR)

# Define the bot token (Replace with your actual token)
TOKEN = '7439562089:AAERgxvEYiLJF_juL68k1nn78negwJ3mNiM'

# Define the chat ID for file uploads (Replace with your actual chat ID)
CHAT_ID = '-1002160780409'

# Global variables
current_recording = None
recording_start_time = None
history = []
scheduler = BackgroundScheduler()

async def start(update: Update, context: CallbackContext):
    await update.message.reply_text('Welcome! The bot is running. Use /help to see available commands.')

async def help_command(update: Update, context: CallbackContext):
    help_text = (
        "/start - Start the bot\n"
        "/help - Show this help message\n"
        "/record <M3U8 link> [<duration>] [<format>] [<resolution>] [<quality>] - Start recording the M3U8 stream\n"
        "/status - Show the current status of the bot\n"
        "/cancel - Cancel the current operation\n"
        "/timing - Show the start time of the recording\n"
        "/history - Show the download history\n"
        "/schedule <time> <M3U8 link> [<duration>] [<format>] [<resolution>] [<quality>] - Schedule a recording"
    )
    await update.message.reply_text(help_text)

async def record(update: Update, context: CallbackContext):
    global current_recording, recording_start_time
    
    if current_recording is not None:
        await update.message.reply_text('A recording is already in progress. Use /cancel to stop it.')
        return

    if len(context.args) < 1:
        await update.message.reply_text('Usage: /record <M3U8 link> [<duration>] [<format>] [<resolution>] [<quality>]')
        return

    m3u8_url = context.args[0]
    duration = context.args[1] if len(context.args) > 1 else '00:00:00'
    file_format = context.args[2] if len(context.args) > 2 else 'mkv'
    resolution = context.args[3] if len(context.args) > 3 else ''
    quality = context.args[4] if len(context.args) > 4 else ''

    timestamp = int(datetime.now().timestamp())
    filename = os.path.join(RECORDINGS_DIR, f'recording_{timestamp}.{file_format}')
    command = ['ffmpeg', '-i', m3u8_url, '-c', 'copy', '-f', file_format, filename]

    if resolution:
        command.insert(-2, f'-s {resolution}')
    if quality:
        command.insert(-2, f'-b:v {quality}')

    current_recording = filename
    recording_start_time = datetime.now()

    try:
        logger.info(f'Starting recording to {filename}')
        process = subprocess.Popen(command)
        process.wait()
        # After recording, upload the file
        await context.bot.send_document(chat_id=CHAT_ID, document=open(filename, 'rb'))
        history.append({'filename': filename, 'timestamp': timestamp})
        await update.message.reply_text(f'Recording finished and uploaded: {filename}')
    except Exception as e:
        logger.error(f'Error during recording: {e}')
        await update.message.reply_text(f'An error occurred: {e}')
    finally:
        current_recording = None
        recording_start_time = None

async def status(update: Update, context: CallbackContext):
    if current_recording:
        start_time = recording_start_time.strftime('%Y-%m-%d %H:%M:%S') if recording_start_time else 'N/A'
        await update.message.reply_text(f'Recording in progress: {current_recording}\nStarted at: {start_time}')
    else:
        await update.message.reply_text('No recording is currently in progress.')

async def cancel(update: Update, context: CallbackContext):
    global current_recording
    
    if current_recording is None:
        await update.message.reply_text('No recording to cancel.')
        return
    
    # Find and terminate the `ffmpeg` process
    for proc in subprocess.Popen(['pgrep', 'ffmpeg'], stdout=subprocess.PIPE).stdout:
        try:
            os.kill(int(proc), signal.SIGKILL)
        except OSError as e:
            logger.error(f'Error killing process: {e}')

    current_recording = None
    await update.message.reply_text('Recording cancelled.')

async def timing(update: Update, context: CallbackContext):
    if recording_start_time:
        await update.message.reply_text(f'Recording started at {recording_start_time.strftime("%Y-%m-%d %H:%M:%S")}')
    else:
        await update.message.reply_text('No recording in progress.')

async def history_command(update: Update, context: CallbackContext):
    if not history:
        await update.message.reply_text('No recordings in history.')
    else:
        history_text = '\n'.join(f'{entry["filename"]} - {datetime.fromtimestamp(entry["timestamp"])}' for entry in history)
        await update.message.reply_text(f'Recording history:\n{history_text}')

async def schedule(update: Update, context: CallbackContext):
    if len(context.args) < 2:
        await update.message.reply_text('Usage: /schedule <time> <M3U8 link> [<duration>] [<format>] [<resolution>] [<quality>]')
        return

    time_str = context.args[0]
    m3u8_url = context.args[1]
    duration = context.args[2] if len(context.args) > 2 else '00:00:00'
    file_format = context.args[3] if len(context.args) > 3 else 'mkv'
    resolution = context.args[4] if len(context.args) > 4 else ''
    quality = context.args[5] if len(context.args) > 5 else ''

    try:
        schedule_time = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
        delta = (schedule_time - datetime.now()).total_seconds()
        if delta <= 0:
            await update.message.reply_text('Scheduled time must be in the future.')
            return
        
        scheduler.add_job(record_stream, 'date', run_date=schedule_time, args=[m3u8_url, duration, file_format, resolution, quality, context])
        await update.message.reply_text(f'Scheduled recording at {schedule_time.strftime("%Y-%m-%d %H:%M:%S")}')
    except ValueError:
        await update.message.reply_text('Time must be in the format: YYYY-MM-DD HH:MM:SS')

async def record_stream(m3u8_url, duration, file_format, resolution, quality, context: CallbackContext):
    timestamp = int(datetime.now().timestamp())
    filename = os.path.join(RECORDINGS_DIR, f'recording_{timestamp}.{file_format}')
    command = ['ffmpeg', '-i', m3u8_url, '-c', 'copy', '-f', file_format, filename]

    if resolution:
        command.insert(-2, f'-s {resolution}')
    if quality:
        command.insert(-2, f'-b:v {quality}')

    try:
        logger.info(f'Starting scheduled recording to {filename}')
        process = subprocess.Popen(command)
        process.wait()
        # After recording, upload the file
        await context.bot.send_document(chat_id=CHAT_ID, document=open(filename, 'rb'))
        history.append({'filename': filename, 'timestamp': timestamp})
    except Exception as e:
        logger.error(f'Error during scheduled recording: {e}')

def main():
    global scheduler
    application = ApplicationBuilder().token(TOKEN).build()
    scheduler.start()

    # Add command handlers
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('help', help_command))
    application.add_handler(CommandHandler('record', record))
    application.add_handler(CommandHandler('status', status))
    application.add_handler(CommandHandler('cancel', cancel))
    application.add_handler(CommandHandler('timing', timing))
    application.add_handler(CommandHandler('history', history_command))
    application.add_handler(CommandHandler('schedule', schedule))
    
    logger.info('Bot is running')
    application.run_polling()

if __name__ == '__main__':
    main()
    
        

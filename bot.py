_':
    main()
import os
import logging
import subprocess
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from telegram import Update, ParseMode
from telegram.ext import Application, CommandHandler, CallbackContext, CallbackQueryHandler
from telegram.ext import CommandHandler

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define the path for recordings
RECORDINGS_DIR = 'recordings'
if not os.path.exists(RECORDINGS_DIR):
    os.makedirs(RECORDINGS_DIR)

# Define the bot token (Replace with your actual token)
TOKEN = '7439562089:AAERgxvEYiLJF_juL68k1nn78negwJ3mNiM'

# Global variables
current_recording = None
recording_start_time = None
history = []

def start(update: Update, context: CallbackContext):
    update.message.reply_text('Welcome! The bot is running. Use /help to see available commands.')

def help_command(update: Update, context: CallbackContext):
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
    update.message.reply_text(help_text)

def record(update: Update, context: CallbackContext):
    global current_recording, recording_start_time
    
    if current_recording is not None:
        update.message.reply_text('A recording is already in progress. Use /cancel to stop it.')
        return

    if len(context.args) < 1:
        update.message.reply_text('Usage: /record <M3U8 link> [<duration>] [<format>] [<resolution>] [<quality>]')
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
        chat_id = 'YOUR_CHAT_ID_HERE'
        context.bot.send_document(chat_id=chat_id, document=open(filename, 'rb'))
        history.append({'filename': filename, 'timestamp': timestamp})
        update.message.reply_text(f'Recording finished and uploaded: {filename}')
    except Exception as e:
        logger.error(f'Error during recording: {e}')
        update.message.reply_text(f'An error occurred: {e}')
    finally:
        current_recording = None
        recording_start_time = None

def status(update: Update, context: CallbackContext):
    if current_recording:
        start_time = recording_start_time.strftime('%Y-%m-%d %H:%M:%S') if recording_start_time else 'N/A'
        update.message.reply_text(f'Recording in progress: {current_recording}\nStarted at: {start_time}')
    else:
        update.message.reply_text('No recording is currently in progress.')

def cancel(update: Update, context: CallbackContext):
    global current_recording
    
    if current_recording is None:
        update.message.reply_text('No recording to cancel.')
        return
    
    # To cancel the recording, we need to terminate the `ffmpeg` process
    for proc in subprocess.Popen(['pgrep', 'ffmpeg'], stdout=subprocess.PIPE).stdout:
        os.kill(int(proc), 9)

    current_recording = None
    update.message.reply_text('Recording cancelled.')

def timing(update: Update, context: CallbackContext):
    if recording_start_time:
        update.message.reply_text(f'Recording started at {recording_start_time.strftime("%Y-%m-%d %H:%M:%S")}')
    else:
        update.message.reply_text('No recording in progress.')

def history_command(update: Update, context: CallbackContext):
    if not history:
        update.message.reply_text('No recordings in history.')
    else:
        history_text = '\n'.join(f'{entry["filename"]} - {datetime.fromtimestamp(entry["timestamp"])}' for entry in history)
        update.message.reply_text(f'Recording history:\n{history_text}')

def schedule(update: Update, context: CallbackContext):
    if len(context.args) < 2:
        update.message.reply_text('Usage: /schedule <time> <M3U8 link> [<duration>] [<format>] [<resolution>] [<quality>]')
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
            update.message.reply_text('Scheduled time must be in the future.')
            return
        
        scheduler.add_job(record_stream, 'date', run_date=schedule_time, args=[m3u8_url, duration, file_format, resolution, quality])
        update.message.reply_text(f'Scheduled recording at {schedule_time.strftime("%Y-%m-%d %H:%M:%S")}')
    except ValueError:
        update.message.reply_text('Time must be in the format: YYYY-MM-DD HH:MM:SS')

def record_stream(m3u8_url, duration, file_format, resolution, quality):
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
        chat_id = 'YOUR_CHAT_ID_HERE'
        context.bot.send_document(chat_id=chat_id, document=open(filename, 'rb'))
        history.append({'filename': filename, 'timestamp': timestamp})
        logger.info(f'Recording finished and uploaded: {filename}')
    except Exception as e:
        logger.error(f'Error during recording: {e}')

def main():
    global scheduler, context
    
    application = Application.builder().token(TOKEN).build()
    scheduler = BackgroundScheduler()
    scheduler.start()

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

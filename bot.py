import os
import logging
import subprocess
from datetime import datetime
from telegram import Update, InputFile
from telegram.ext import Application, CommandHandler, CallbackContext, MessageHandler, filters

# Set up logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Define bot token (replace 'YOUR_NEW_BOT_TOKEN' with your actual bot token)
TOKEN = 'YOUR_NEW_BOT_TOKEN'

# Global variables
current_m3u8_link = None
recording_start_time = None
download_process = None
mux_process = None

# Define the bot commands
async def start(update: Update, context: CallbackContext):
    await update.message.reply_text("Welcome! Use /help to see available commands.")

async def help_command(update: Update, context: CallbackContext):
    help_text = (
        "/start - Start the bot\n"
        "/help - Show this help message\n"
        "/record <M3U8 link> - Start recording the M3U8 stream\n"
        "/status - Show the current status of the bot\n"
        "/cancel - Cancel the current operation\n"
        "/timing - Show the start time of the recording\n"
    )
    await update.message.reply_text(help_text)

async def record(update: Update, context: CallbackContext):
    global current_m3u8_link, recording_start_time, download_process, mux_process
    
    if download_process or mux_process:
        await update.message.reply_text("Another recording or muxing process is already running. Please wait or cancel the current operation.")
        return
    
    if not context.args:
        await update.message.reply_text("Please provide an M3U8 link.")
        return
    
    m3u8_link = context.args[0]
    current_m3u8_link = m3u8_link
    recording_start_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    filename = "output.ts"
    await update.message.reply_text(f"Recording started for {m3u8_link}. Please wait...")

    # Start recording
    download_process = subprocess.Popen(['ffmpeg', '-i', m3u8_link, '-c', 'copy', filename], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # Monitor progress
    for line in iter(download_process.stderr.readline, b''):
        line = line.decode('utf-8')
        if 'time=' in line:
            # Extract the time part of the progress log
            time_info = line.split('time=')[-1].split(' ')[0]
            time_parts = time_info.split(':')
            elapsed_time = int(time_parts[0]) * 3600 + int(time_parts[1]) * 60 + float(time_parts[2])
            await update.message.reply_text(f"Download progress: {elapsed_time:.2f}s")

    download_process.wait()
    if download_process.returncode == 0:
        await update.message.reply_text("Recording complete! Muxing the file...")
        mux_file(filename, update)
    else:
        await update.message.reply_text("Recording failed.")
        download_process = None

async def mux_file(filename, update: Update):
    global mux_process
    
    mp4_filename = filename.replace('.ts', '.mp4')
    mux_process = subprocess.Popen(['ffmpeg', '-i', filename, '-c', 'copy', mp4_filename], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # Monitor progress
    for line in iter(mux_process.stderr.readline, b''):
        line = line.decode('utf-8')
        if 'time=' in line:
            # Extract the time part of the progress log
            time_info = line.split('time=')[-1].split(' ')[0]
            time_parts = time_info.split(':')
            elapsed_time = int(time_parts[0]) * 3600 + int(time_parts[1]) * 60 + float(time_parts[2])
            await update.message.reply_text(f"Muxing progress: {elapsed_time:.2f}s")

    mux_process.wait()
    if mux_process.returncode == 0:
        await update.message.reply_text("Muxing complete! Uploading the file...")
        upload_file(mp4_filename, update)
    else:
        await update.message.reply_text("Muxing failed.")
        mux_process = None

async def upload_file(mp4_filename, update: Update):
    with open(mp4_filename, 'rb') as file:
        await update.message.reply_document(document=InputFile(file, filename=mp4_filename))
    os.remove(mp4_filename)  # Clean up
    await update.message.reply_text("File uploaded successfully!")
    global current_m3u8_link, recording_start_time
    current_m3u8_link = None
    recording_start_time = None

async def cancel(update: Update, context: CallbackContext):
    global download_process, mux_process

    if download_process:
        download_process.terminate()
        download_process = None
        await update.message.reply_text("Download process has been cancelled.")
    elif mux_process:
        mux_process.terminate()
        mux_process = None
        await update.message.reply_text("Muxing process has been cancelled.")
    else:
        await update.message.reply_text("No ongoing process to cancel.")

async def status(update: Update, context: CallbackContext):
    if current_m3u8_link:
        elapsed_time = datetime.now() - datetime.strptime(recording_start_time, '%Y-%m-%d %H:%M:%S')
        await update.message.reply_text(f"Current M3U8 Link: {current_m3u8_link}\n"
                                 f"Recording Start Time: {recording_start_time}\n"
                                 f"Elapsed Time: {elapsed_time}\n"
                                 f"Processes - Download: {'Running' if download_process else 'Not Running'}, "
                                 f"Muxing: {'Running' if mux_process else 'Not Running'}")
    else:
        await update.message.reply_text("No ongoing recording process.")

async def timing(update: Update, context: CallbackContext):
    if recording_start_time:
        await update.message.reply_text(f"Recording started at: {recording_start_time}")
    else:
        await update.message.reply_text("No ongoing recording process.")

def main():
    try:
        # Create Application object with bot token
        application = Application.builder().token(TOKEN).build()

        # Register handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("record", record))
        application.add_handler(CommandHandler("cancel", cancel))
        application.add_handler(CommandHandler("status", status))
        application.add_handler(CommandHandler("timing", timing))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, record))

        # Start the Bot
        application.run_polling()

    except Exception as e:
        logger.error(f"An error occurred: {e}")

if __name__ == '__main__':
    main()

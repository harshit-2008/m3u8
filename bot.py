TOKEN = ''
import os
import logging
import subprocess
from datetime import datetime, timedelta
from telegram import Update, InputFile
from telegram.ext import Application, CommandHandler, CallbackContext, MessageHandler, filters

# Set up logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Define bot token and admin user ID (replace 'YOUR_NEW_BOT_TOKEN' and 'YOUR_TELEGRAM_ID' with actual values)
TOKEN = '7439562089:AAERgxvEYiLJF_juL68k1nn78negwJ3mNiM'
ADMIN_ID = 6066102279  # Replace with your Telegram User ID for admin commands

# Global variables
current_m3u8_link = None
recording_start_time = None
download_process = None
mux_process = None
download_history = []

# Define the bot commands
async def start(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("You are not authorized to use this bot.")
        return
    await update.message.reply_text("Welcome! Use /help to see available commands.")

async def help_command(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("You are not authorized to use this bot.")
        return
    help_text = (
        "/start - Start the bot\n"
        "/help - Show this help message\n"
        "/record <M3U8 link> [<duration>] [<format>] [<resolution>] [<quality>] - Start recording the M3U8 stream\n"
        "/status - Show the current status of the bot\n"
        "/cancel - Cancel the current operation\n"
        "/timing - Show the start time of the recording\n"
        "/history - Show the download history\n"
        "/schedule <time> <M3U8 link> [<duration>] [<format>] [<resolution>] [<quality>] - Schedule a recording\n"
    )
    await update.message.reply_text(help_text)

async def record(update: Update, context: CallbackContext):
    global current_m3u8_link, recording_start_time, download_process, mux_process
    
    user_id = update.message.from_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("You are not authorized to use this bot.")
        return
    
    if download_process or mux_process:
        await update.message.reply_text("Another recording or muxing process is already running. Please wait or cancel the current operation.")
        return
    
    if not context.args:
        await update.message.reply_text("Please provide an M3U8 link.")
        return
    
    m3u8_link = context.args[0]
    duration = int(context.args[1]) if len(context.args) > 1 else 10  # Default to 10 seconds if not specified
    format_ = context.args[2] if len(context.args) > 2 else 'mp4'  # Default to 'mp4' if not specified
    resolution = context.args[3] if len(context.args) > 3 else None  # Default to original resolution if not specified
    quality = context.args[4] if len(context.args) > 4 else None  # Default to original quality if not specified
    
    current_m3u8_link = m3u8_link
    recording_start_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    filename = f"output.{format_}"
    
    command_args = ['ffmpeg', '-i', m3u8_link, '-t', str(duration), '-c', 'copy']
    if resolution:
        command_args += ['-s', resolution]
    if quality:
        command_args += ['-b:v', quality]
    command_args.append(filename)
    
    await update.message.reply_text(f"Recording started for {m3u8_link} for {duration} seconds. Please wait...")
    
    try:
        # Start recording
        download_process = subprocess.Popen(
            command_args,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        
        # Monitor progress
        while True:
            line = download_process.stderr.readline()
            if not line and download_process.poll() is not None:
                break
            line = line.decode('utf-8')
            logger.info(line)  # Log ffmpeg output
            
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
            logger.error("Recording process failed with return code: %d", download_process.returncode)
            download_process = None

    except Exception as e:
        logger.error(f"An error occurred during the recording process: {e}")
        await update.message.reply_text("An error occurred during the recording process.")
        # Clean up
        if os.path.exists(filename):
            os.remove(filename)

async def mux_file(filename, update: Update):
    global mux_process
    
    mp4_filename = filename.replace('.ts', '.mp4')
    try:
        mux_process = subprocess.Popen(
            ['ffmpeg', '-i', filename, '-c', 'copy', mp4_filename],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        
        # Monitor progress
        while True:
            line = mux_process.stderr.readline()
            if not line and mux_process.poll() is not None:
                break
            line = line.decode('utf-8')
            logger.info(line)  # Log ffmpeg output
            
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
            logger.error("Muxing process failed with return code: %d", mux_process.returncode)
            mux_process = None

    except Exception as e:
        logger.error(f"An error occurred during the muxing process: {e}")
        await update.message.reply_text("An error occurred during the muxing process.")
        # Clean up
        if os.path.exists(filename):
            os.remove(filename)
        if os.path.exists(mp4_filename):
            os.remove(mp4_filename)

async def upload_file(mp4_filename, update: Update):
    try:
        with open(mp4_filename, 'rb') as file:
            await update.message.reply_document(document=InputFile(file, filename=mp4_filename))
        os.remove(mp4_filename)  # Clean up
        await update.message.reply_text("File uploaded successfully!")
        global current_m3u8_link, recording_start_time
        current_m3u8_link = None
        recording_start_time = None
        download_history.append({
            'link': current_m3u8_link,
            'start_time': recording_start_time,
            'filename': mp4_filename
        })

    except Exception as e:
        logger.error(f"An error occurred while uploading the file: {e}")
        await update.message.reply_text("An error occurred while uploading the file.")

async def cancel(update: Update, context: CallbackContext):
    global download_process, mux_process

    user_id = update.message.from_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("You are not authorized to use this bot.")
        return

    try:
        if download_process:
            download_process.terminate()
            download_process.wait()
            download_process = None
            await update.message.reply_text("Download process has been cancelled.")
        elif mux_process:
            mux_process.terminate()
            mux_process.wait()
            mux_process = None
            await update.message.reply_text("Muxing process has been cancelled.")
        else:
            await update.message.reply_text("No ongoing process to cancel.")
    except Exception as e:
        logger.error(f"An error occurred during the cancel operation: {e}")
        await update.message.reply_text("An error occurred during the cancel operation.")

async def status(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("You are not authorized to use this bot.")
        return

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
    user_id = update.message.from_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("You are not authorized to use this bot.")
        return

    if recording_start_time:
        await update.message.reply_text(f"Recording started at: {recording_start_time}")
    else:
        await update.message.reply_text("No ongoing recording process.")

async def history(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("You are not authorized to use this bot.")
        return
    
    if not download_history:
        await update.message.reply_text("No history available.")
        return
    
    history_text = "Download History:\n"
    for record in download_history:
        history_text += (f"Link: {record['link']}\n"
                        f"Start Time: {record['start_time']}\n"
                        f"File: {record['filename']}\n\n")
    await update.message.reply_text(history_text)

async def schedule(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("You are not authorized to use this bot.")
        return
    
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /schedule <time> <M3U8 link> [<duration>] [<format>] [<resolution>] [<quality>]")
        return
    
    schedule_time_str = context.args[0]
    try:
        schedule_time = datetime.strptime(schedule_time_str, '%Y-%m-%d %H:%M:%S')
    except ValueError:
        await update.message.reply_text("Invalid time format. Use 'YYYY-MM-DD HH:MM:SS'.")
        return
    
    m3u8_link = context.args[1]
    duration = int(context.args[2]) if len(context.args) > 2 else 10
    format_ = context.args[3] if len(context.args) > 3 else 'mp4'
    resolution = context.args[4] if len(context.args) > 4 else None
    quality = context.args[5] if len(context.args) > 5 else None
    
    delay = (schedule_time - datetime.now()).total_seconds()
    if delay <= 0:
        await update.message.reply_text("Scheduled time must be in the future.")
        return
    
    await update.message.reply_text(f"Scheduled recording for {m3u8_link} at {schedule_time_str}.")
    
    # Schedule the recording
    context.job_queue.run_once(
        lambda context: context.bot.send_message(chat_id=ADMIN_ID, text=f"Recording started for {m3u8_link} at {schedule_time_str}...") or record(update, context),
        delay
    )

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
        application.add_handler(CommandHandler("history", history))
        application.add_handler(CommandHandler("schedule", schedule))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, record))

        # Start the Bot
        logger.info("Starting the bot...")
        application.run_polling()

    except Exception as e:
        logger.error(f"An error occurred: {e}")

if __name__ == '__main__':
    main()

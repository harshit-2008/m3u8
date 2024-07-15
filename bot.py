import logging
import asyncio
import ffmpeg
import os
from datetime import datetime, timedelta
from telegram import Update, InputFile
from telegram.ext import Application, CommandHandler, CallbackContext, MessageHandler, filters
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger

# Bot Token and Admin ID
TOKEN = '7439562089:AAERgxvEYiLJF_juL68k1nn78negwJ3mNiM'
ADMIN_ID = 6066102279 # Replace with your Telegram user ID

# Configure logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Create directories for recordings
if not os.path.exists('recordings'):
    os.makedirs('recordings')

# Initialize the scheduler
scheduler = AsyncIOScheduler()
scheduler.start()

# Dictionary to keep track of ongoing recordings
recordings = {}

# Dictionary to keep track of scheduled recordings
schedules = {}

# Dictionary to keep track of completed recordings for history
history = []

def admin_required(func):
    """Decorator to check if the user is an admin."""
    async def wrapper(update: Update, context: CallbackContext):
        if update.message.from_user.id == ADMIN_ID:
            return await func(update, context)
        else:
            await update.message.reply_text('Sorry, but you are not allowed to use this command.')
    return wrapper

async def start(update: Update, context: CallbackContext):
    await update.message.reply_text('Welcome to the Live Recorder Bot! Use /record to start recording a live stream or /schedule to schedule a recording.')

@admin_required
async def record(update: Update, context: CallbackContext):
    if len(context.args) != 5:
        await update.message.reply_text('Usage: /record <m3u8_url> <duration> <format> <resolution> <quality>')
        return
    
    m3u8_url, duration, format, resolution, quality = context.args

    # Validate inputs
    try:
        duration = int(duration)
    except ValueError:
        await update.message.reply_text('Invalid duration. Please enter a valid number of seconds.')
        return

    valid_formats = ['mp4', 'mkv', 'avi']
    if format not in valid_formats:
        await update.message.reply_text(f'Invalid format. Supported formats are: {", ".join(valid_formats)}.')
        return

    valid_resolutions = ['640x360', '1280x720', '1920x1080']
    if resolution not in valid_resolutions:
        await update.message.reply_text(f'Invalid resolution. Supported resolutions are: {", ".join(valid_resolutions)}.')
        return

    valid_qualities = ['low', 'medium', 'high']
    if quality not in valid_qualities:
        await update.message.reply_text(f'Invalid quality. Supported qualities are: {", ".join(valid_qualities)}.')
        return

    resolution_dict = {
        '640x360': '360',
        '1280x720': '720',
        '1920x1080': '1080'
    }

    quality_dict = {
        'low': '1',
        'medium': '2',
        'high': '3'
    }

    # Build the ffmpeg command
    output_file = f'recordings/recording_{update.message.message_id}.{format}'
    ffmpeg_command = [
        'ffmpeg',
        '-i', m3u8_url,
        '-t', str(duration),
        '-vf', f'scale={resolution}',
        '-c:v', 'libx264',
        '-crf', quality_dict[quality],
        '-preset', 'fast',
        '-c:a', 'aac',
        '-strict', 'experimental',
        output_file
    ]

    # Add recording job to dictionary
    recordings[update.message.message_id] = {
        'm3u8_url': m3u8_url,
        'duration': duration,
        'format': format,
        'resolution': resolution,
        'quality': quality,
        'start_time': datetime.now(),
        'status': 'Started',
        'file': output_file
    }

    try:
        # Start the recording process
        await update.message.reply_text(f'Recording started for {duration} seconds. Format: {format.upper()}, Resolution: {resolution}, Quality: {quality.capitalize()}.')

        process = await asyncio.create_subprocess_exec(*ffmpeg_command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        await process.communicate()

        # Update recording job status
        recordings[update.message.message_id]['status'] = 'Completed'

        # Send the recorded video file
        with open(output_file, 'rb') as video:
            await update.message.reply_document(document=InputFile(video, filename=f'recording_{update.message.message_id}.{format}'))

        # Add to history
        history.append(recordings[update.message.message_id])

        # Remove the local recording file
        os.remove(output_file)
        del recordings[update.message.message_id]
    except Exception as e:
        logger.error(f'An error occurred while recording: {e}')
        await update.message.reply_text('An error occurred while trying to record the stream.')
        recordings[update.message.message_id]['status'] = 'Failed'

@admin_required
async def schedule(update: Update, context: CallbackContext):
    if len(context.args) != 6:
        await update.message.reply_text('Usage: /schedule <m3u8_url> <start_time> <duration> <format> <resolution> <quality>')
        return

    m3u8_url, start_time_str, duration, format, resolution, quality = context.args

    # Validate inputs
    try:
        duration = int(duration)
        start_time = datetime.strptime(start_time_str, '%Y-%m-%d %H:%M:%S')
    except ValueError:
        await update.message.reply_text('Invalid time format. Use YYYY-MM-DD HH:MM:SS for start_time.')
        return

    valid_formats = ['mp4', 'mkv', 'avi']
    if format not in valid_formats:
        await update.message.reply_text(f'Invalid format. Supported formats are: {", ".join(valid_formats)}.')
        return

    valid_resolutions = ['640x360', '1280x720', '1920x1080']
    if resolution not in valid_resolutions:
        await update.message.reply_text(f'Invalid resolution. Supported resolutions are: {", ".join(valid_resolutions)}.')
        return

    valid_qualities = ['low', 'medium', 'high']
    if quality not in valid_qualities:
        await update.message.reply_text(f'Invalid quality. Supported qualities are: {", ".join(valid_qualities)}.')
        return

    resolution_dict = {
        '640x360': '360',
        '1280x720': '720',
        '1920x1080': '1080'
    }

    quality_dict = {
        'low': '1',
        'medium': '2',
        'high': '3'
    }

    # Schedule the recording job
    async def job():
        output_file = f'recordings/scheduled_recording_{update.message.message_id}.{format}'
        ffmpeg_command = [
            'ffmpeg',
            '-i', m3u8_url,
            '-t', str(duration),
            '-vf', f'scale={resolution}',
            '-c:v', 'libx264',
            '-crf', quality_dict[quality],
            '-preset', 'fast',
            '-c:a', 'aac',
            '-strict', 'experimental',
            output_file
        ]
        try:
            await update.message.reply_text(f'Scheduled recording started for {duration} seconds. Format: {format.upper()}, Resolution: {resolution}, Quality: {quality.capitalize()}.')
            process = await asyncio.create_subprocess_exec(*ffmpeg_command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            await process.communicate()
            await update.message.reply_document(document=InputFile(output_file, filename=f'scheduled_recording_{update.message.message_id}.{format}'))
            history.append({
                'm3u8_url': m3u8_url,
                'duration': duration,
                'format': format,
                'resolution': resolution,
                'quality': quality,
                'start_time': start_time,
                'status': 'Completed',
                'file': output_file
            })
            os.remove(output_file)
        except Exception as e:
            logger.error(f'An error occurred while recording: {e}')
            await update.message.reply_text('An error occurred while trying to record the stream.')

    job_id = f'scheduled_{update.message.message_id}'
    scheduler.add_job(job, DateTrigger(run_date=start_time), id=job_id, name=f'Scheduled Recording {update.message.message_id}')
    schedules[job_id] = {
        'm3u8_url': m3u8_url,
        'start_time': start_time,
        'duration': duration,
        'format': format,
        'resolution': resolution,
        'quality': quality,
        'status': 'Scheduled'
    }
    await update.message.reply_text(f'Recording scheduled successfully. Job ID: {job_id}')

@admin_required
async def status(update: Update, context: CallbackContext):
    if len(context.args) != 1:
        await update.message.reply_text('Usage: /status <message_id>')
        return

    try:
        message_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text('Invalid message ID. Please enter a valid number.')
        return

    if message_id in recordings:
        record_info = recordings[message_id]
        status_message = (
            f"Recording Status:\n"
            f"**M3U8 URL**: {escape_markdown(record_info['m3u8_url'])}\n"
            f"**Duration**: {record_info['duration']} seconds\n"
            f"**Format**: {record_info['format'].upper()}\n"
            f"**Resolution**: {record_info['resolution']}\n"
            f"**Quality**: {record_info['quality'].capitalize()}\n"
            f"**Start Time**: {record_info['start_time'].strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"**Status**: {record_info['status']}"
        )
        await update.message.reply_text(status_message, parse_mode='MarkdownV2')
    else:
        await update.message.reply_text('No ongoing recording with this message ID.')

@admin_required
async def timing(update: Update, context: CallbackContext):
    if len(context.args) != 1:
        await update.message.reply_text('Usage: /timing <job_id>')
        return

    try:
        job_id = context.args[0]
        job = scheduler.get_job(job_id)
        if job:
            schedule_info = schedules[job_id]
            timing_message = (
                f"Scheduled Recording Timing:\n"
                f"**M3U8 URL**: {escape_markdown(schedule_info['m3u8_url'])}\n"
                f"**Start Time**: {schedule_info['start_time'].strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"**Duration**: {schedule_info['duration']} seconds\n"
                f"**Format**: {schedule_info['format'].upper()}\n"
                f"**Resolution**: {schedule_info['resolution']}\n"
                f"**Quality**: {schedule_info['quality'].capitalize()}\n"
                f"**Status**: {schedule_info['status']}"
            )
            await update.message.reply_text(timing_message, parse_mode='MarkdownV2')
        else:
            await update.message.reply_text('No scheduled recording with this Job ID.')
    except Exception as e:
        logger.error(f'An error occurred while getting the timing: {e}')
        await update.message.reply_text('An error occurred while trying to get the timing.')

@admin_required
async def history(update: Update, context: CallbackContext):
    if not history:
        await update.message.reply_text('No history available.')
        return
    
    history_messages = []
    for record in history:
        history_messages.append(
            f"**Recording ID**: {record['file']}\n"
            f"**M3U8 URL**: {escape_markdown(record['m3u8_url'])}\n"
            f"**Duration**: {record['duration']} seconds\n"
            f"**Format**: {record['format'].upper()}\n"
            f"**Resolution**: {record['resolution']}\n"
            f"**Quality**: {record['quality'].capitalize()}\n"
            f"**Start Time**: {record['start_time'].strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"**Status**: {record['status']}\n\n"
        )
    
    history_text = '\n'.join(history_messages)
    await update.message.reply_text(f"**Recording History:**\n\n{history_text}", parse_mode='MarkdownV2')

def main():
    """Run the bot."""
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("record", record))
    application.add_handler(CommandHandler("schedule", schedule))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("timing", timing))
    application.add_handler(CommandHandler("history", history))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, start))  # To handle any other text messages

    application.run_polling()

if __name__ == '__main__':
    main()

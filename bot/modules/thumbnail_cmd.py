from os import path as ospath
from pyrogram.handlers import MessageHandler
from pyrogram.filters import command
from pyrogram.types import Message
from bot import bot, user_data, DATABASE_URL, config_dict
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.message_utils import sendMessage
from bot.helper.ext_utils.db_handler import database
from aiofiles.os import makedirs, path as aiopath

async def set_thumbnail(client, message: Message):
    user_id = message.from_user.id if message.from_user else message.sender_chat.id

    # Check if command has -s thumb
    text = message.text or message.caption or ""
    args = text.split()
    if "-s" not in args or "thumb" not in args:
        await sendMessage("Usage: Send or reply to a photo with `/cmd -s thumb` to set a custom thumbnail.", message)
        return

    photo = None
    if message.reply_to_message and message.reply_to_message.photo:
        photo = message.reply_to_message.photo
    elif message.photo:
        photo = message.photo
    elif message.reply_to_message and message.reply_to_message.document and message.reply_to_message.document.mime_type.startswith('image/'):
        photo = message.reply_to_message.document
    elif message.document and message.document.mime_type.startswith('image/'):
        photo = message.document

    if not photo:
        await sendMessage("No photo found! Reply to a photo or send a photo with `/cmd -s thumb`.", message)
        return

    path = ospath.join('thumbnails', f'{user_id}.jpg')
    await makedirs('thumbnails', exist_ok=True)
    msg = await sendMessage("Downloading thumbnail...", message)

    if hasattr(photo, 'file_id'):
        await client.download_media(message=photo.file_id, file_name=path)
    else:
        # In case it's a message object
        if getattr(message, 'reply_to_message', None):
            await client.download_media(message=message.reply_to_message, file_name=path)
        else:
            await client.download_media(message=message, file_name=path)

    if user_id not in user_data:
        user_data[user_id] = {}
    user_data[user_id]['thumb'] = path
    if DATABASE_URL:
        await database.update_user_doc(user_id, 'thumb', path)

    await msg.edit("✅ Custom Thumbnail saved successfully!")

bot.add_handler(MessageHandler(set_thumbnail, filters=command("cmd") & CustomFilters.authorized))

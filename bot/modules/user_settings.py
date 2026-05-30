from aiofiles.os import path as aiopath, makedirs
from ast import literal_eval
from asyncio import sleep, gather, Event, wait_for, wrap_future
from functools import partial
from html import escape
from os import path as ospath, getcwd
from pyrogram import Client
from pyrogram.filters import command, regex, create, user
from pyrogram.handlers import CallbackQueryHandler, MessageHandler
from pyrogram.types import CallbackQuery, Message
from time import time

from bot import bot, bot_loop, bot_dict, bot_lock, user_data, config_dict, DATABASE_URL, GLOBAL_EXTENSION_FILTER
from bot.helper.ext_utils.bot_utils import update_user_ldata, UserDaily, new_thread, new_task, is_premium_user
from bot.helper.ext_utils.commons_check import UseCheck
from bot.helper.ext_utils.conf_loads import intialize_savebot
from bot.helper.ext_utils.db_handler import DbManager
from bot.helper.ext_utils.files_utils import clean_target
from bot.helper.ext_utils.help_messages import UsetString
from bot.helper.ext_utils.media_utils import createThumb
from bot.helper.ext_utils.status_utils import get_readable_time, get_readable_file_size
from bot.helper.ext_utils.telegram_helper import TeleContent
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.telegram_helper.button_build import ButtonMaker
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.message_utils import sendMessage, auto_delete_message, sendPhoto, editPhoto, deleteMessage, editMessage, sendCustom


handler_dict = {}


async def get_user_settings(from_user, data: str, uset_data: str):
    msg = ''
    buttons = ButtonMaker()
    user_id = from_user.id
    thumbpath = ospath.join('thumbnails', f'{user_id}.jpg')
    rclone_path = ospath.join('rclone', f'{user_id}.conf')
    token_pickle = ospath.join('tokens', f'{user_id}.pickle')
    user_dict = user_data.get(user_id, {})
    premium_left = status_user = daily_limit = ''
    image = None

    if not data:
        sendpm, buttonkey = (' ✓', '✓ Send PM') if user_dict.get('enable_pm') else (' ✘', 'Send PM')
        buttons.button_data(buttonkey, f'userset {user_id} enable_pm')

        sendss, buttonkey = (' ✓', '✓ Screenshot') if user_dict.get('enable_ss') else (' ✘', 'Screenshot')
        buttons.button_data(buttonkey, f'userset {user_id} enable_ss')

        AD = config_dict['AS_DOCUMENT']
        ltype, buttonkey = ('Document', '✓ As Document') if not user_dict and AD or user_dict.get('as_doc') else ('Media', 'As Document')
        buttons.button_data(buttonkey, f'userset {user_id} as_doc')

        MG = config_dict['MEDIA_GROUP']
        mediagroup, buttonkey = (' ✓', '✓ As Group') if user_dict.get('media_group') or 'media_group' not in user_dict and MG else (' ✘', 'As Group')
        buttons.button_data(buttonkey, f'userset {user_id} media_group')

        premsg, buttonkey = (prename, '✓ Prename') if (prename := user_dict.get('prename')) else (' ✘', 'Prename')
        buttons.button_data(buttonkey, f'userset {user_id} setdata prename')

        sufmsg, buttonkey = (sufname, '✓ Sufname') if (sufname := user_dict.get('sufname')) else (' ✘', 'Sufname')
        buttons.button_data(buttonkey, f'userset {user_id} setdata sufname')

        rmmsg, buttonkey = (' ✓', '✓ Remname') if user_dict.get('remname') else (' ✘', 'Remname')
        buttons.button_data(buttonkey, f'userset {user_id} setdata remname')

        thumbmsg, buttonkey = (' ✓', '✓ Thumbnail') if await aiopath.exists(thumbpath) else (' ✘', 'Thumbnail')
        buttons.button_data(buttonkey, f'userset {user_id} setdata thumb')

        dumpch, buttonkey = (f'<code>{user_dict.get("dump_ch")}</code>', ' Dump CH') if user_dict.get('dump_ch') else (' ✘', 'Dump CH')
        buttons.button_data(buttonkey, f'userset {user_id} setdata dump_ch')

        gdxmsg, buttonkey = (' ✓', '✓ Custom GDX') if await aiopath.exists(token_pickle) else (' ✘', 'Custom GDX')
        buttons.button_data(buttonkey, f'userset {user_id} gdtool')

        rccmsg, buttonkey = (' ✓', '✓ RClone') if await aiopath.exists(rclone_path) else (' ✘', 'RClone')
        buttons.button_data(buttonkey, f'userset {user_id} rctool')

        metadata, buttonkey = (' ✓', '✓ Metadata') if user_dict.get('metadata') else (' ✘', 'Metadata')
        buttons.button_data(buttonkey, f'userset {user_id} setdata metadata')

        default_upload = user_dict.get('default_upload', '') or config_dict['DEFAULT_UPLOAD']
        du = 'GDrive API' if default_upload == 'gd' else 'RClone'
        dub = 'GDRIVE' if default_upload != 'gd' else 'RCLONE'
        buttons.button_data(f'Engine {dub}', f'userset {user_id} {default_upload}', 'header')

        YOPT = config_dict['YT_DLP_OPTIONS']
        buttonkey = '✓ YT-DLP'
        if user_dict.get('yt_opt'):
            yto = f'\n<b><code>{escape(user_dict["yt_opt"])}</code></b>'
        elif 'yt_opt' not in user_dict and (YOPT := config_dict['YT_DLP_OPTIONS']):
            yto = f'\n<b><code>{escape(YOPT)}</code></b>'
        else:
            buttonkey = 'YT-DLP'
            yto = ' ✘'
        buttons.button_data(buttonkey, f'userset {user_id} setdata yt_opt')

        capmode = user_dict.get('caption_style', 'mono')
        buttons.button_data('✓ Caption' if user_dict.get('captions') else 'Caption', f'userset {user_id} capmode')

        buttons.button_data('Zip Mode', f'userset {user_id} zipmode')

        sesmsg, buttonkey = (' ✓', '✓ Session String') if user_dict.get('session_string') else (' ✘', 'Session String')
        buttons.button_data(buttonkey, f'userset {user_id} setdata session_string')

        if ext_filters := user_dict.get('excluded_extensions'):
            ex_ex = f'<code>{", ".join(ext_filters)}</code>'
        elif 'excluded_extensions' not in user_dict and GLOBAL_EXTENSION_FILTER:
            ex_ex = f'<code>{", ".join(GLOBAL_EXTENSION_FILTER)}</code>'
        else:
            ex_ex = ''
        buttons.button_data('✓ Extensions Filters' if ex_ex else 'Extensions Filters', f'userset {user_id} setdata excluded_extensions')

        custom_cap = ' ✓' if user_dict.get('captions') else ' ✘'


    return msg, image, buttons.build_menu(2) if hasattr(buttons, 'build_menu') else buttons

async def update_user_settings(query: CallbackQuery, data: str=None, uset_data: str=None):
    text, image, button = await get_user_settings(query.from_user, data, uset_data)
    if not image:
        if await aiopath.exists(thumb := ospath.join('thumbnails', f'{query.from_user.id}.jpg')):
            image = thumb
        else:
            image = config_dict['IMAGE_USETIINGS']
    await editPhoto(text, query.message, image, button)


async def set_user_settings(_, message: Message, query: CallbackQuery, key: str):
    user_id = message.from_user.id
    handler_dict[user_id] = False
    value: str = message.text
    if (key == 'dump_ch' and value.isdigit() or value.startswith('-100')):
        value = int(value)
    elif key == 'excluded_extensions':
        fx = value.split()
        value = ['aria2', '!qB']
        for x in fx:
            x = x.lstrip('.')
            value.append(x.strip().lower())
    await gather(update_user_ldata(user_id, key, value), deleteMessage(message))
    if key == 'dump_ch':
        await update_user_settings(query, 'setdata', 'dump_ch')
    else:
        match key:
            case 'index_url' | 'token_pickle' | 'gdrive_id':
                data = 'gdtool'
            case 'captions':
                data = 'capmode'
            case 'rclone_path':
                data = 'rctool'
            case _:
                data = ''
        if key == 'session_string':
            await intialize_savebot(value, True, user_id)
            async with bot_lock:
                save_bot = bot_dict[user_id]['SAVEBOT']
            if not save_bot:
                msg = await sendMessage('Something went wrong, or invalid string!', message)
                await update_user_ldata(user_id, key, '')
                bot_loop.create_task(auto_delete_message(message, msg, stime=5))
        await update_user_settings(query, data)


async def set_thumb(_, message: Message, query: CallbackQuery):
    user_id = query.from_user.id
    handler_dict[user_id] = False
    msg = await sendMessage('<i>Processing, please wait...</i>', message)
    des_dir = await createThumb(message, user_id)
    await gather(update_user_ldata(user_id, 'thumb', des_dir), deleteMessage(message, msg), update_user_settings(query))
    if DATABASE_URL:
        await DbManager().update_user_doc(user_id, 'thumb', des_dir)


async def add_rclone_pickle(_, message: Message, query: CallbackQuery, key: str):
    user_id = message.from_user.id
    handler_dict[user_id] = False
    file_path, ext_file = ('rclone', '.conf') if key == 'rclone_config' else ('tokens', '.pickle')
    fpath = ospath.join(getcwd(), file_path)
    await makedirs(fpath, exist_ok=True)
    if message.document.file_name.endswith(ext_file):
        des_dir = ospath.join(fpath, f'{user_id}{ext_file}')
        msg = await sendMessage('<i>Processing, please wait...</i>', message)
        await message.download(file_name=des_dir)
        qdata = 'rctool' if key == 'rclone_config' else 'gdtool'
        await gather(update_user_ldata(user_id, file_path, ospath.join(file_path, f'{user_id}{ext_file}')), deleteMessage(message, msg), update_user_settings(query, qdata))
        if DATABASE_URL:
            await DbManager().update_user_doc(user_id, key, des_dir)
    else:
        msg = await sendMessage(f'Invalid *{ext_file} file!', message)
        await gather(update_user_settings(query, 'setdata', key), auto_delete_message(message, msg, stime=5))


@new_thread
async def edit_user_settings(client: Client, query: CallbackQuery):
    message = query.message
    user_id = query.from_user.id
    data = query.data.split()
    user_dict = user_data.get(user_id, {})
    premi_features = ['caption', 'dump_ch', 'gdrive_id', 'media_group', 'prename', 'sufname', 'remname', 'metadata', 'session_string', 'enable_pm', 'enable_ss']
    pre_data = data[3] if data[2] == 'setdata' else data[2]
    if user_id != int(data[1]):
        await query.answer('Not Yours!', True)
        return
    match data[2]:
        case 'setdata':
            handler_dict[user_id] = False
            await query.answer()
            if data[3] in ('dump_ch', 'metadata') and len(data) == 5:
                key = 'log_title' if data[3] == 'dump_ch' else 'clean_metadata'
                await update_user_ldata(user_id, key, literal_eval(data[4]))
            await update_user_settings(query, 'setdata', data[3])
        case 'gd' | 'rc' as value:
            du = 'rc' if value == 'gd' else 'gd'
            await gather(query.answer(), update_user_ldata(user_id, 'default_upload', du))
            await update_user_settings(query)
        case 'back':
            handler_dict[user_id] = False
            await gather(query.answer(), update_user_settings(query))
        case 'rem_prename' | 'rem_sufname' | 'rem_dump_ch' | 'rem_remname' | 'rem_metadata' | 'rem_session_string' | 'rem_yt_opt' | 'rem_index_url' \
            | 'rem_gdrive_id' | 'rem_captions' | 'rem_excluded_extensions' | 'rem_rclone_path' as value:
            qdata = uset_data = ''
            match value:
                case 'rem_dump_ch':
                    await update_user_ldata(user_id, 'log_title', False)
                case 'rem_session_string':
                    if savebot := bot_dict[user_id]['SAVEBOT']:
                        await savebot.stop()
                case 'rem_captions':
                    qdata = 'capmode'
                    await update_user_ldata(user_id, 'fnamecap', True)
                case 'rem_rclone_path':
                    qdata = 'rctool'
                case 'rem_index_url' | 'rem_gdrive_id':
                    qdata = 'gdtool'
            if value in ('rem_rclone_path', 'rem_gdrive_id') and value in user_data.get(user_id, {}):
                del user_data[user_id][value]
                if DATABASE_URL:
                    await DbManager().update_user_data(user_id)
            else:
                await update_user_ldata(user_id, value[4:], '')
            await gather(query.answer(), update_user_settings(query, qdata, uset_data))
        case 'enable_pm' | 'enable_ss' | 'as_doc' | 'media_group' | 'fnamecap' | 'stop_duplicate' | 'use_sa' as value:
            qdata = uset_data = ''
            await update_user_ldata(user_id, value, not user_dict.get(value, False))
            if value == 'fnamecap':
                qdata = 'capmode'
            if value in ('stop_duplicate', 'use_sa'):
                qdata = 'gdtool'
            await gather(query.answer(), update_user_settings(query, qdata, uset_data))
        case 'capmode' | 'gdtool' | 'rctool' as value:
            await gather(query.answer(), update_user_settings(query, value))
        case 'zipmode':
            try:
                zmode = data[3]
            except:
                zmode = user_dict.get('zipmode', 'zfolder')
            if zmode == user_dict.get('zipmode', '') and len(data) == 4:
                await query.answer('Already Selected!', True)
                return
            await gather(query.answer(), update_user_ldata(user_id, 'zipmode', zmode))
            await update_user_settings(query, 'zipmode', zmode)
        case 'capmono' | 'capitalic' | 'capbold' | 'capnormal' as value:
            await update_user_ldata(user_id, 'caption_style', value.lstrip('cap'))
            await gather(query.answer(), update_user_settings(query, 'capmode'))
        case 'close':
            handler_dict[user_id] = False
            await gather(query.answer(), deleteMessage(message, message.reply_to_message))
        case 'rem_thumb' | 'rem_rclone_config' | 'rem_token_pickle' as value:
            match value:
                case 'rem_thumb':
                    path = ospath.join('thumbnails', f'{user_id}.jpg')
                case 'rem_rclone_config':
                    path = ospath.join('rclone', f'{user_id}.conf')
                case _:
                    path = ospath.join('tokens', f'{user_id}.pickle')
            key = value.lstrip('rem_')
            await update_user_ldata(user_id, key, '')
            if await aiopath.exists(path):
                await gather(query.answer(), clean_target(path))
                await update_user_settings(query)
                if DATABASE_URL:
                    await DbManager().update_user_doc(user_id, key)
            else:
                await gather(query.answer('Old Settings', True), update_user_settings(query))
        case 'prepare':
            match data[3]:
                case 'rclone_config' | 'token_pickle':
                    await query.answer()
                    photo, document = False, True
                    pfunc = partial(add_rclone_pickle, query=query, key=data[3])
                case 'thumb':
                    await query.answer()
                    photo, document = True, False
                    pfunc = partial(set_thumb, query=query)
                case _:
                    handler_dict[user_id] = True
                    await query.answer('Don\'t forget add me to your chat!', True) if data[3] == 'dump_ch' else await query.answer()
                    photo = document = False
                    pfunc = partial(set_user_settings, query=query, key=data[3])
            await gather(update_user_settings(query, data[2], data[3]), event_handler(client, query, pfunc, photo, document))


async def event_handler(client: Client, query: CallbackQuery, pfunc: partial, photo: bool=False, document: bool=False):
    user_id = query.from_user.id
    handler_dict[user_id] = True
    start_time = time()

    async def event_filter(_, __, event):
        if photo:
            mtype = event.photo
        elif document:
            mtype = event.document
        else:
            mtype = event.text
        user = event.from_user or event.sender_chat
        return bool(user.id == user_id and event.chat.id == query.message.chat.id and mtype)

    handler = client.add_handler(MessageHandler(pfunc, filters=create(event_filter)), group=-1)
    while handler_dict[user_id]:
        await sleep(0.5)
        if time() - start_time > 60:
            handler_dict[user_id] = False
            await update_user_settings(query)
    client.remove_handler(*handler)


@new_task
async def user_settings(client, message: Message):
    from_user = message.from_user
    handler_dict[from_user.id] = False
    if fmsg := await UseCheck(message).run():
        await auto_delete_message(message, fmsg)
        return

    text = message.text or message.caption or ""
    args = text.split()
    if "-s" in args and "thumb" in args:
        user_id = from_user.id
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
            await sendMessage("No photo found! Reply to a photo or send a photo with `-s thumb`.", message)
            return

        path = ospath.join('thumbnails', f'{user_id}.jpg')
        await makedirs('thumbnails', exist_ok=True)
        dl_msg = await sendMessage("Downloading thumbnail...", message)

        if hasattr(photo, 'file_id'):
            await client.download_media(message=photo.file_id, file_name=path)
        else:
            if getattr(message, 'reply_to_message', None):
                await client.download_media(message=message.reply_to_message, file_name=path)
            else:
                await client.download_media(message=message, file_name=path)

        if user_id not in user_data:
            user_data[user_id] = {}
        user_data[user_id]['thumb'] = path
        if config_dict['DATABASE_URL']:
            from bot.helper.ext_utils.db_handler import DbManager
            await DbManager().update_user_doc(user_id, 'thumb', path)

        await editMessage("✅ Custom Thumbnail saved successfully!", dl_msg)

    result = await get_user_settings(from_user, None, None)
    if result is None:
        LOGGER.error("get_user_settings returned None for user: " + str(from_user.id))
        await message.reply("❌ Failed to load user settings. Please try again.")
        return
    msg, image, buttons = result
    if await aiopath.exists(thumb := ospath.join('thumbnails', f'{message.from_user.id}.jpg')):
        image = thumb
    await sendPhoto(msg, message, image or config_dict['IMAGE_USETIINGS'], buttons)






@new_task
async def reset_daily_limit(_, message: Message):
    reply_to = message.reply_to_message
    args = message.text.split()
    if not reply_to and len(args) == 1:
        await sendMessage('Reply to a user or send user ID to reset daily limit.', message)
        return
    if reply_to:
        user_id = reply_to.from_user.id
    elif len(args) > 1:
        user_id = int(args[1])
    await gather(update_user_ldata(user_id, 'daily_limit', 1), update_user_ldata(user_id, 'reset_limit', time() + 86400))
    msg = await sendMessage('Daily limit has been reset.', message)
    await auto_delete_message(message, msg)


@new_task
async def send_users_settings(client: Client, message: Message):
    contents = []
    msg = ''
    if len(user_data) == 0:
        await sendMessage('No user data!', message)
        return
    for index, (uid, data) in enumerate(user_data.items(), start=1):
        if data.get('is_sudo') and 'sudo_left' in data and data['sudo_left'] - time() <= 0:
            del user_data[uid]['sudo_left']
            await update_user_ldata(uid, 'is_sudo', False)
        uname = user_data[uid].get('user_name')
        msg += f'<b><a href="https://t.me/{uname}">{uname}</a></b>\n'
        msg += f'⁍ <b>User ID:</b> <code>{uid}</code>\n'
        for key, value in data.items():
            if key in ('session_token', 'session_time') or value == '':
                continue
            if key == 'reset_limit':
                value -= time()
                value = get_readable_time(0 if value <= 1 else value)
            elif key == 'daily_limit':
                value = f'{get_readable_file_size(value)}/{config_dict["DAILY_LIMIT_SIZE"]}GB'
            elif key in ('premium_left', 'sudo_left'):
                value = f'{get_readable_time(value - time())}'
            elif key in ('caption_style', 'zipmode'):
                value = str(value).title()
            elif key in ['thumb', 'rclone_config', 'token_pickle']:
                value = 'Exists' if value else 'Not Exists'
            elif key in ['dump_ch', 'yt_opt', 'index_url', 'gdrive_id', 'prename', 'sufname', 'metadata']:
                value = f'<code>{value}</code>'
            elif str(value).lower() == 'true' or (key in ['session_string', 'remname', 'captions'] and value):
                value = 'Yes'
            elif str(value).lower() == 'false':
                value = 'No'
            if key != 'user_name' and value != '':
                msg += f'⁍ <b>{key.replace("_", " ").title()}:</b> {value}\n'
        contents.append(f'{str(index).zfill(3)}. {msg}\n')
        msg = ''
    tele = TeleContent(message, max_page=5, direct=False)
    tele.set_data(contents, f'<b>FOUND {len(contents)} USERS SETTINGS DATA</b>')
    text, buttons = await tele.get_content('usettings')
    msg = await sendMessage(text, message, buttons)
    event = Event()

    @new_thread
    async def __event_handler():
        pfunc = partial(users_handler, event=event, tele=tele)
        handler = client.add_handler(CallbackQueryHandler(pfunc, filters=regex('^usettings') & user(message.from_user.id)), group=-1)
        try:
            await wait_for(event.wait(), timeout=180)
        except:
            pass
        finally:
            client.remove_handler(*handler)

    await wrap_future(__event_handler())
    await deleteMessage(msg, message)


async def users_handler(_, query: CallbackQuery, event=Event, tele=TeleContent):
    message = query.message
    data = query.data.split()
    if data[2] == 'close':
        event.set()
        if tele:
            tele.cancel()
        await deleteMessage(message, message.reply_to_message)
    else:
        tdata = int(data[4]) if data[2] == 'foot' else int(data[3])
        text, buttons = await tele.get_content('usettings', data[2], tdata)
        if data[2] == 'page':
            await query.answer(f'Total Page ~ {tele.pages}', True)
            return
        if not buttons:
            await query.answer(text, True)
            return
        await gather(query.answer(), editMessage(text, message, buttons))


from bot import CMD_SUFFIX

bot.add_handler(MessageHandler(send_users_settings, filters=command(BotCommands.UsersCommand) & CustomFilters.sudo))
bot.add_handler(MessageHandler(reset_daily_limit, filters=command(BotCommands.DailyResetCommand) & CustomFilters.sudo))
bot.add_handler(MessageHandler(user_settings, filters=command([BotCommands.UserSetCommand, f'us{CMD_SUFFIX}', 'us']) & CustomFilters.authorized))
bot.add_handler(CallbackQueryHandler(edit_user_settings, filters=regex('^userset')))

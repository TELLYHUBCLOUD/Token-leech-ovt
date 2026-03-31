from __future__ import annotations
from aiofiles.os import path as aiopath, rename as aiorename, makedirs
from aioshutil import copy
from asyncio import sleep, gather
from logging import getLogger
from natsort import natsorted
from os import path as ospath, walk
from PIL import Image
from pyrogram.errors import FloodWait, RPCError
from pyrogram.types import InputMediaVideo, InputMediaDocument, InputMediaPhoto, Message
from re import match as re_match
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type, RetryError
from time import time

from bot import bot, bot_dict, bot_lock, config_dict, DEFAULT_SPLIT_SIZE, LOGGER
from bot.helper.ext_utils.bot_utils import sync_to_async, default_button
from bot.helper.ext_utils.files_utils import clean_unwanted, clean_target, get_path_size, is_archive, get_base_name
from bot.helper.ext_utils.media_utils import create_thumbnail, take_ss, get_document_type, get_media_info, get_audio_thumb, post_media_info, GenSS
from bot.helper.ext_utils.shortenurl import short_url
from bot.helper.listeners import tasks_listener as task
from bot.helper.stream_utils.file_properties import gen_link
from bot.helper.telegram_helper.button_build import ButtonMaker
from bot.helper.telegram_helper.message_utils import deleteMessage, handle_message


LOGGER = getLogger(__name__)


class TgUploader:
    def __init__(self, listener: task.TaskListener, path: str, size: int):
        self._last_uploaded = 0
        self._processed_bytes = 0
        self._listener = listener
        self._path = path
        self._start_time = time()
        self._is_cancelled = False
        self._thumb = self._listener.thumb or ospath.join('thumbnails', f'{self._listener.user_id}.jpg')
        self._msgs_dict = {}
        self._is_corrupted = False
        self._size = size
        self._media_dict = {'videos': {}, 'documents': {}}
        self._last_msg_in_group = False
        self._client = None
        self._send_msg = None
        self._up_path = ''
        self._leech_log = config_dict['LEECH_LOG']

    async def _upload_progress(self, current, _):
        if self._is_cancelled:
            self._client.stop_transmission()
        chunk_size = current - self._last_uploaded
        self._last_uploaded = current
        self._processed_bytes += chunk_size

    async def upload(self, o_files, m_size):
        await self._user_settings()
        await self._msg_to_reply()
        corrupted_files = total_files = 0
        for dirpath, _, files in sorted(await sync_to_async(walk, self._path)):
            if dirpath.endswith('/yt-dlp-thumb'):
                continue
            for file_ in natsorted(files):
                self._up_path = ospath.join(dirpath, file_)
                if file_.lower().endswith(tuple(self._listener.extensionFilter)) or file_.startswith('Thumb'):
                    if not file_.startswith('Thumb'):
                        await clean_target(self._up_path)
                    continue
                try:
                    f_size = await get_path_size(self._up_path)
                    if self._listener.seed and file_ in o_files and f_size in m_size:
                        continue
                    if f_size == 0:
                        corrupted_files += 1
                        LOGGER.error('%s size is zero, telegram don\'t upload zero size files', self._up_path)
                        continue
                    if self._is_cancelled:
                        return
                    caption = await self._prepare_file(file_, dirpath)
                    if self._last_msg_in_group:
                        group_lists = [x for v in self._media_dict.values() for x in v.keys()]
                        match = re_match(r'.+(?=\.0*\d+$)|.+(?=\.part\d+\..+$)', self._up_path)
                        if not match or match and match.group(0) not in group_lists:
                            for key, value in list(self._media_dict.items()):
                                for subkey, msgs in list(value.items()):
                                    if len(msgs) > 1:
                                        await self._send_media_group(msgs, subkey, key)
                    self._last_msg_in_group = False
                    self._last_uploaded = 0
                    await self._upload_file(caption, file_)
                    total_files += 1
                    if self._is_cancelled:
                        return
                    if not self._is_corrupted and (self._listener.isSuperChat or self._leech_log):
                        self._msgs_dict[self._send_msg.link] = file_
                    await sleep(3)
                except Exception as err:
                    if isinstance(err, RetryError):
                        LOGGER.info('Total Attempts: %s', err.last_attempt.attempt_number, exc_info=True)
                        corrupted_files += 1
                        self._is_corrupted = True
                        err = err.last_attempt.exception()
                    LOGGER.error('%s. Path: %s', err, self._up_path)
                    corrupted_files += 1
                    if self._is_cancelled:
                        return
                    continue
                finally:
                    if not self._is_cancelled and await aiopath.exists(self._up_path) and (not self._listener.seed or self._listener.newDir or
                        dirpath.endswith('/splited_files_mltb') or '/copied_mltb/' in self._up_path):
                        await clean_target(self._up_path)

        for key, value in list(self._media_dict.items()):
            for subkey, msgs in list(value.items()):
                if len(msgs) > 1:
                    await self._send_media_group(msgs, subkey, key)
        if self._is_cancelled:
            return
        if self._listener.seed and not self._listener.newDir:
            await clean_unwanted(self._path)
        if total_files == 0:
            await self._listener.onUploadError(f"No files to upload or in blocked list ({', '.join(self._listener.extensionFilter[2:])})!")
            return
        if total_files <= corrupted_files:
            await self._listener.onUploadError('Files Corrupted or unable to upload. Check logs!')
            return
        LOGGER.info('Leech Completed: %s', self._listener.name)
        await self._listener.onUploadComplete(None, self._size, self._msgs_dict, total_files, corrupted_files)

    @retry(wait=wait_exponential(multiplier=2, min=4, max=8), stop=stop_after_attempt(4), retry=retry_if_exception_type(Exception))
    async def _upload_file(self, caption, file, force_document=False):
        if self._thumb and not await aiopath.exists(self._thumb):
            self._thumb = None
        thumb, ss_image = self._thumb, None
        if self._is_cancelled:
            return
        try:
            async with bot_lock:
                self._client = (bot_dict['USERBOT'] if bot_dict['IS_PREMIUM'] and await get_path_size(self._up_path) > DEFAULT_SPLIT_SIZE
                                or bot_dict['USERBOT'] and config_dict['USERBOT_LEECH'] else bot)
            is_video, is_audio, is_image = await get_document_type(self._up_path)
            if not is_image and thumb is None:
                file_name = ospath.splitext(file)[0]
                thumb_path = ospath.join(self._path, 'yt-dlp-thumb', f'{file_name}.jpg')
                if await aiopath.isfile(thumb_path):
                    thumb = thumb_path
                elif is_audio and not is_video:
                    thumb = await get_audio_thumb(self._up_path)
            if is_video:
                duration = (await get_media_info(self._up_path))[0]
                ss_image = await self._gen_ss(self._up_path)
                if self._listener.screenShots:
                    await self._send_screenshots()
                if not thumb:
                    thumb = await create_thumbnail(self._up_path, duration)

            if self._listener.as_doc or force_document or (not is_video and not is_audio and not is_image):
                key = 'documents'
                if self._is_cancelled:
                    return
                self._send_msg = await self._client.send_document(chat_id=self._send_msg.chat.id,
                                                                  document=self._up_path,
                                                                  thumb=thumb,
                                                                  caption=caption,
                                                                  disable_notification=True,
                                                                  progress=self._upload_progress,
                                                                  reply_to_message_id=self._send_msg.id)
            elif is_video:
                key = 'videos'
                if thumb:
                    print(1)
                    with Image.open(thumb) as img:
                        width, height = img.size
                else:
                    print(2)
                    width, height = 480, 320
                if not self._up_path.upper().endswith(('.MKV', '.MP4')):
                    dirpath, file_ = ospath.split(self._up_path)
                    if self._listener.seed and not self._listener.newDir and not dirpath.endswith('/splited_files_mltb'):
                        dirpath = ospath.join(dirpath, 'copied_mltb')
                        await makedirs(dirpath, exist_ok=True)
                        new_path = ospath.join(dirpath, f'{ospath.splitext(file_)[0]}.mp4')
                        self._up_path = await copy(self._up_path, new_path)
                    else:
                        new_path = f'{ospath.splitext(self._up_path)[0]}.mp4'
                        await aiorename(self._up_path, new_path)
                        self._up_path = new_path
                if self._is_cancelled:
                    return
                self._send_msg = await self._client.send_video(chat_id=self._send_msg.chat.id,
                                                               video=self._up_path,
                                                               caption=caption,
                                                               duration=duration,
                                                               width=width,
                                                               height=height,
                                                               thumb=thumb,
                                                               supports_streaming=True,
                                                               disable_notification=True,
                                                               progress=self._upload_progress,
                                                               reply_to_message_id=self._send_msg.id)
            elif is_audio:
                key = 'audios'
                duration, artist, title = await get_media_info(self._up_path)
                if self._is_cancelled:
                    return
                self._send_msg = await self._client.send_audio(chat_id=self._send_msg.chat.id,
                                                               audio=self._up_path,
                                                               caption=caption,
                                                               duration=duration,
                                                               performer=artist,
                                                               title=title,
                                                               thumb=thumb,
                                                               disable_notification=True,
                                                               progress=self._upload_progress,
                                                               reply_to_message_id=self._send_msg.id)
            else:
                key = 'photos'
                if self._is_cancelled:
                    return
                self._send_msg = await bot.send_photo(chat_id=self._send_msg.chat.id,
                                                      photo=self._up_path,
                                                      caption=caption,
                                                      disable_notification=True,
                                                      progress=self._upload_progress,
                                                      reply_to_message_id=self._send_msg.id)
            if self._is_cancelled:
                return
            await self._final_message(ss_image, bool(is_video or is_audio))
            if self._send_pm:
                await self._copy_Leech(self._listener.user_id, self._send_msg)
            if self._listener.upDest:
                await self._copy_Leech(self._listener.upDest, self._send_msg)

            if not self._is_cancelled and self._media_group and (self._send_msg.video or self._send_msg.document):
                if match := re_match(r'.+(?=\.0*\d+$)|.+(?=\.part\d+\..+$)', self._up_path):
                    subkey = match.group(0)
                    if subkey in self._media_dict[key].keys():
                        self._media_dict[key][subkey].append(self._send_msg)
                    else:
                        self._media_dict[key][subkey] = [self._send_msg]
                    msgs = self._media_dict[key][subkey]
                    if len(msgs) == 10:
                        await self._send_media_group(msgs, subkey, key)
                    else:
                        self._last_msg_in_group = True

            if not self._thumb and thumb:
                await clean_target(thumb)
        except FloodWait as f:
            LOGGER.warning(f, exc_info=True)
            await sleep(f.value * 1.2)
            return await self._upload_file(caption, file, force_document)
        except Exception as err:
            if not self._thumb and thumb:
                await clean_target(thumb)
            err_type = 'RPCError: ' if isinstance(err, RPCError) else ''
            LOGGER.error('%s%s. Path: %s', err_type, err, self._up_path)

            err_str = str(err)
            if 'CHANNEL_INVALID' in err_str or 'PEER_ID_INVALID' in err_str:
                if self._client != bot:
                    LOGGER.error(f'Userbot could not access chat. Falling back to Main Bot... Path: {self._up_path}')
                    self._client = bot
                    return await self._upload_file(caption, file, force_document)
                raise err
            if 'Telegram says: [400' in err_str and key != 'documents':
                LOGGER.error('Retrying As Document. Path: %s', self._up_path, exc_info=True)
                return await self._upload_file(caption, file, True)
            raise err

    async def _user_settings(self):
        self._media_group = self._listener.user_dict.get('media_group', False) or ('media_group' not in self._listener.user_dict and config_dict['MEDIA_GROUP'])
        self._cap_mode = self._listener.user_dict.get('caption_style', 'mono')
        self._log_title = self._listener.user_dict.get('log_title', False)
        self._send_pm = self._listener.user_dict.get('enable_pm', False) and (self._listener.isSuperChat or self._leech_log)
        self._enable_ss = self._listener.user_dict.get('enable_ss', False)
        self._user_caption = self._listener.user_dict.get('captions', False)
        self._user_fnamecap = self._listener.user_dict.get('fnamecap', True)
        if config_dict['AUTO_THUMBNAIL']:
            for dirpath, _, files in await sync_to_async(walk, self._path):
                for file in files:
                    filepath = ospath.join(dirpath, file)
                    if file.startswith('Thumb') and (await get_document_type(filepath))[-1]:
                        self._thumb = filepath
                        break

    @property
    def speed(self):
        try:
            return self._processed_bytes / (time() - self._start_time)
        except:
            return 0

    @property
    def processed_bytes(self):
        return self._processed_bytes

    async def cancel_task(self):
        self._is_cancelled = True
        LOGGER.info('Cancelling Upload: %s', self._listener.name)
        await self._listener.onUploadError('Upload stopped by user!')

    # ================================================== UTILS ==================================================
    async def _prepare_file(self, file_, dirpath):
        caption = self._caption_mode(file_)
        if len(file_) > 60:
            if is_archive(file_):
                name = get_base_name(file_)
                ext = file_.split(name, 1)[1]
            elif match := re_match(r'.+(?=\..+\.0*\d+$)|.+(?=\.part\d+\..+$)', file_):
                name = match.group(0)
                ext = file_.split(name, 1)[1]
            elif len(fsplit := ospath.splitext(file_)) > 1:
                name, ext = fsplit[0], fsplit[1]
            else:
                name, ext = file_, ''
            name = name[:60 - len(ext)]
            if self._listener.seed and not self._listener.newDir and not dirpath.endswith('/splited_files_mltb'):
                dirpath = ospath.join(dirpath, 'copied_mltb')
                await makedirs(dirpath, exist_ok=True)
                new_path = ospath.join(dirpath, f'{name}{ext}')
                self._up_path = await copy(self._up_path, new_path)
            else:
                new_path = ospath.join(dirpath, f'{name}{ext}')
                await aiorename(self._up_path, new_path)
                self._up_path = new_path
        return caption

    def _caption_mode(self, file):
        match self._cap_mode:
            case 'italic':
                caption = f'<i>{file}</i>'
            case 'bold':
                caption = f'<b>{file}</b>'
            case 'normal':
                caption = file
            case 'mono':
                caption = f'<code>{file}</code>'
        if self._user_caption:
            caption = f'''{caption}\n\n{self._user_caption}''' if self._user_fnamecap else self._user_caption
        return caption

    async def _gen_ss(self, vid_path):
        if not self._enable_ss or self._is_cancelled:
            return
        ss = GenSS(self._listener.message, vid_path)
        await ss.file_ss()
        if ss.error:
            return
        return ss.rimage
    # ===========================================================================================================

    # ================================================= MESSAGE =================================================
    @handle_message
    async def _msg_to_reply(self):
        if self._leech_log and self._leech_log != self._listener.message.chat.id:
            caption = f'<b>▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n{self._listener.name}\n▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬</b>'
            if self._thumb and await aiopath.exists(self._thumb):
                self._send_msg: Message = await bot.send_photo(self._leech_log, photo=self._thumb, caption=caption)
            else:
                self._send_msg: Message = await bot.send_message(self._leech_log, caption, disable_web_page_preview=True)
            if config_dict['LEECH_INFO_PIN']:
                await self._send_msg.pin(both_sides=True)
        else:
            self._send_msg: Message = await bot.get_messages(self._listener.message.chat.id, self._listener.mid)
            if not self._send_msg or not self._send_msg.chat:
                self._send_msg = self._listener.message
        if self._send_msg and self._log_title and self._listener.upDest:
            await self._copy_Leech(self._listener.upDest, self._send_msg)

    @handle_message
    async def _send_media_group(self, msgs: list[Message], subkey: str, key: str):
        msgs_list = await msgs[0].reply_to_message.reply_media_group(media=self._get_input_media(subkey, key),
                                                                     quote=True, disable_notification=True)
        if self._send_pm:
            await self._copy_media_group(self._listener.user_id, msgs_list)
        if self._listener.upDest:
            await self._copy_media_group(self._listener.upDest, msgs_list)
        for msg in msgs:
            self._msgs_dict.pop(msg.link, None)
            await deleteMessage(msg)
        del self._media_dict[key][subkey]
        if self._listener.isSuperChat or self._leech_log:
            for m in msgs_list:
                self._msgs_dict[m.link] = m.caption.split('\n')[0] + ' ~ (Grouped)'
        self._send_msg = msgs_list[-1]

    @handle_message
    async def _send_screenshots(self):
        if isinstance(self._listener.screenShots, str):
            ss_nb = int(self._listener.screenShots)
        else:
            ss_nb = 10
        outputs = await take_ss(self._up_path, ss_nb)
        inputs = []
        if outputs:
            for m in outputs:
                if await aiopath.exists(m):
                    cap = m.rsplit('/', 1)[-1]
                    inputs.append(InputMediaPhoto(m, cap))
                else:
                    outputs.remove(m)
        if outputs:
            msgs_list = await self._send_msg.reply_media_group(media=inputs, quote=True, disable_notification=True)
            if self._send_pm:
                await self._copy_media_group(self._listener.user_id, msgs_list)
            if self._listener.upDest:
                await self._copy_media_group(self._listener.upDest, msgs_list)
            self._send_msg = msgs_list[-1]
            await gather(*[clean_target(m) for m in outputs])

    @handle_message
    async def _copy_media_group(self, chat_id: int, msgs: list[Message]):
        captions = [self._caption_mode(msg.caption.split('\n')[0]) for msg in msgs]
        await bot.copy_media_group(chat_id=chat_id, from_chat_id=msgs[0].chat.id, message_id=msgs[0].id, captions=captions)

    @handle_message
    async def _copy_Leech(self, chat_id: int, message: Message):
        reply_markup = await default_button(message) if config_dict['SAVE_MESSAGE'] and self._listener.isSuperChat else message.reply_markup
        return await message.copy(chat_id, disable_notification=True, reply_markup=reply_markup,
                                  reply_to_message_id=message.reply_to_message.id if chat_id == message.chat.id else None)

    @handle_message
    async def _final_message(self, ss_image, media_info: bool=False):
        self._buttons = ButtonMaker()
        media_result = await post_media_info(self._up_path, self._size, ss_image) if media_info else None
        await clean_target(ss_image)
        if media_result:
            self._buttons.button_link('Media Info', media_result)
        if config_dict['SAVE_MESSAGE'] and self._listener.isSuperChat:
            self._buttons.button_data('Save Message', 'save', 'footer')

        stream_dl_links = await gen_link(self._send_msg)
        for mode, link in zip(['Stream', 'Download'], stream_dl_links):
            if link:
                self._buttons.button_link(mode, await sync_to_async(short_url, link, self._listener.user_id), 'header')

        # Vercel stream player webhook intercept
        if getattr(self._listener, 'vidMode', None) and self._listener.vidMode[0] == 'vid_stream' and self._listener.vidMode[2].get('is_stream', True):
            # Fallback to direct download links generated by Pyrogram (bot downloads) if stream generator is not enabled globally
            video_url_for_vercel = stream_dl_links[1] or stream_dl_links[0]
            if video_url_for_vercel:
                v_url = config_dict.get('VERCEL_URL', '').rstrip('/') or 'https://vercel-steam-mod.vercel.app'
                v_api = config_dict.get('VERCEL_API', '')
                try:
                    import json
                    import base64
                    import aiohttp
                    from bot.helper.ext_utils.status_utils import get_readable_file_size

                    file_name_title = self._send_msg.caption.split('\n')[0] if self._send_msg.caption else "Video_Stream.mkv"

                    # 1. Base64 payload encoding for fallback URLs
                    payload = {
                        "video_url": video_url_for_vercel,
                        "title": file_name_title,
                        "poster_url": "" # Thumbnails generated natively by video player
                    }
                    json_str = json.dumps(payload, separators=(',', ':'))
                    base64_data = base64.b64encode(json_str.encode('utf-8')).decode('utf-8')

                    # 2. Vercel Player links fallback
                    vercel_watch = f"{v_url}/watch?data={base64_data}"
                    vercel_dl = f"{v_url}/download?data={base64_data}"

                    # 3. Call REST API /api/v1/generate if needed
                    api_url = f"{v_url}/api/v1/generate"
                    headers = {
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {v_api}"
                    }
                    async with aiohttp.ClientSession() as session:
                        async with session.post(api_url, headers=headers, json=payload, timeout=10) as resp:
                            if resp.status == 200:
                                api_data = await resp.json()
                                if api_data.get('success'):
                                    vercel_watch = api_data['data'].get('watch_url', vercel_watch)
                                    vercel_dl = api_data['data'].get('download_url', vercel_dl)

                except Exception as e:
                    LOGGER.error(f"Vercel Stream Generation Error: {e}")

                # Rewrite the caption as requested even if Vercel API failed (we have fallback base64 URLs)
                new_caption = (f"<b>Stream File Successfully Processed</b>\n\n"
                               f"<b>Name:</b> <code>{file_name_title}</code> <b>Size:</b> {get_readable_file_size(self._size)}\n\n"
                               f"<b>Stream Link:</b>\n{vercel_watch}\n\n"
                               f"<b>Download Link:</b>\n{vercel_dl}\n\n"
                               f"‣ ᴘᴏᴡᴇʀᴇᴅ ʙʏ: Sᴇᴄʀᴇᴄᴛ 𝐁ᴏᴛ 𝐔ᴘᴅᴀᴛᴇs")

                self._buttons.button_link('▶ Vercel Stream', await sync_to_async(short_url, vercel_watch, self._listener.user_id), 'header')
                self._buttons.button_link('⬇ Vercel DL', await sync_to_async(short_url, vercel_dl, self._listener.user_id), 'header')

                try:
                    await self._send_msg.edit_caption(caption=new_caption)
                except Exception as caption_err:
                    LOGGER.error(f"Error editing caption for Stream Mode: {caption_err}")

        self._send_msg = await bot.get_messages(self._send_msg.chat.id, self._send_msg.id)
        if (buttons := self._buttons.build_menu(2)) and (cmsg := await self._send_msg.edit_reply_markup(buttons)):
            self._send_msg = cmsg

    def _get_input_media(self, subkey: str, key: str):
        imlist = []
        for msg in self._media_dict[key][subkey]:
            caption = self._caption_mode(msg.caption.split('\n')[0])
            if key == 'videos':
                input_media = InputMediaVideo(media=msg.video.file_id, caption=caption)
            else:
                input_media = InputMediaDocument(media=msg.document.file_id, caption=caption)
            imlist.append(input_media)
        return imlist
    # ===========================================================================================================

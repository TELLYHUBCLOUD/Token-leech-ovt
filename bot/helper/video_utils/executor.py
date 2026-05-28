from __future__ import annotations
from aiofiles import open as aiopen
from aiofiles.os import path as aiopath, makedirs, listdir
from aioshutil import move
from ast import literal_eval
from asyncio import create_subprocess_exec, sleep, gather, Event
from asyncio.subprocess import PIPE
from natsort import natsorted
from os import path as ospath, walk
from time import time

from bot import config_dict, task_dict, task_dict_lock, queue_dict_lock, non_queued_dl, LOGGER, VID_MODE, FFMPEG_NAME
from bot.helper.ext_utils.bot_utils import sync_to_async, cmd_exec, new_task
from bot.helper.ext_utils.files_utils import get_path_size, clean_target
from bot.helper.ext_utils.links_utils import get_url_name
from bot.helper.ext_utils.media_utils import get_document_type, get_media_info, FFProgress
from bot.helper.ext_utils.task_manager import check_running_tasks
from bot.helper.listeners import tasks_listener as task
from bot.helper.mirror_utils.status_utils.ffmpeg_status import FFMpegStatus
from bot.helper.mirror_utils.status_utils.queue_status import QueueStatus
from bot.helper.telegram_helper.message_utils import sendStatusMessage, update_status_message
from bot.helper.video_utils.extra_selector import ExtraSelect


async def get_metavideo(video_file):
    stdout, stderr, rcode = await cmd_exec(['ffprobe', '-hide_banner', '-print_format', 'json', '-show_format', '-show_streams', video_file])
    if rcode != 0:
        LOGGER.error(stderr)
        return {}, {}
    metadata = literal_eval(stdout)
    return metadata.get('streams', {}), metadata.get('format', {})


class VidEcxecutor(FFProgress):
    def __init__(self, listener: task.TaskListener, path: str, gid: str, metadata=False):
        self.data = None
        self.event = Event()
        self.listener = listener
        self.path = path
        self.name = ''
        self.outfile = ''
        self.size = 0
        self._metadata = metadata
        self._up_path = path
        self._gid = gid
        self._start_time = time()
        self._files = []
        self._qual = {'1080p': '1920', '720p': '1280', '540p': '960', '480p': '854', '360p': '640'}
        super().__init__()
        self.is_cancel = False

    async def _queue(self, update=False):
        if self._metadata:
            add_to_queue, event = await check_running_tasks(self.listener.mid)
            if add_to_queue:
                LOGGER.info('Added to Queue/Download: %s', self.name)
                async with task_dict_lock:
                    task_dict[self.listener.mid] = QueueStatus(self.listener, self.size, self._gid, 'dl')
                await self.listener.onDownloadStart()
                if update:
                    await sendStatusMessage(self.listener.message)
                await event.wait()
                async with task_dict_lock:
                    if self.listener.mid not in task_dict:
                        self.is_cancel = True
                        return
            async with queue_dict_lock:
                non_queued_dl.add(self.listener.mid)

    async def execute(self):
        self._is_dir = await aiopath.isdir(self.path)
        self.mode, self.name, kwargs = self.listener.vidMode
        if not self._metadata and self.mode in config_dict['DISABLE_MULTI_VIDTOOLS']:
            if path := await self._get_video():
                self.path = path
            else:
                return self._up_path
        if self._metadata:
            if not self.name:
                self.name = get_url_name(self.path)
            if not self.name.upper().endswith(('MP4', 'MKV')):
                self.name += '.mkv'
            try:
                self.size = int(self._metadata[1]['size'])
            except Exception as e:
                LOGGER.error(e)
                await self.listener.onDownloadError('Invalid data, check the link!')
                return

        try:
            match self.mode:
                case 'vid_vid':
                    return await self._merge_vids(**kwargs)
                case 'vid_aud':
                    return await self._merge_auds(**kwargs)
                case 'vid_sub':
                    return await self._merge_subs(**kwargs)
                case 'trim':
                    return await self._vid_trimmer(**kwargs)
                case 'watermark':
                    return await self._vid_marker(**kwargs)
                case 'compress':
                    return await self._vid_compress(**kwargs)
                case 'subsync':
                    return await self._subsync(**kwargs)
                case 'rmstream':
                    return await self._rm_stream()
                case 'extract':
                    return await self._vid_extract()
                case 'vid_stream':
                    return await self._vid_stream(**kwargs)
                case _:
                    return await self._vid_convert()
        except Exception as e:
            LOGGER.error(e, exc_info=True)
        return self._up_path

    async def _vid_stream(self, **kwargs):
        # We process this identically to vid_sub (or returning up_path)
        # so files proceed to Telegram upload. The actual webhook call to Vercel
        # will happen in the TelegramUploader once we have the stream links.
        # But we DO need to move files to up_path. If user sent extra files via UI,
        # we just return them so they upload as well.
        if vid_list := kwargs.get('vid_list'):
            base_dir = self.path if self._is_dir else ospath.dirname(self.path)
            for media_file in vid_list:
                if await aiopath.exists(media_file):
                    await move(media_file, ospath.join(base_dir, ospath.basename(media_file)))
        return self._up_path

    @new_task
    async def _start_handler(self, *args):
        await sleep(0.5)
        await ExtraSelect(self).get_buttons(*args)

    async def _send_status(self, status='wait'):
        async with task_dict_lock:
            task_dict[self.listener.mid] = FFMpegStatus(self.listener, self, self._gid, status)
        if self._metadata and status == 'wait':
            await sendStatusMessage(self.listener.message)

    async def _get_files(self):
        file_list = []
        if self._metadata:
            file_list.append(self.path)
        elif await aiopath.isfile(self.path):
            if (await get_document_type(self.path))[0]:
                file_list.append(self.path)
        else:
            for dirpath, _, files in await sync_to_async(walk, self.path):
                for file in natsorted(files):
                    file = ospath.join(dirpath, file)
                    if (await get_document_type(file))[0]:
                        file_list.append(file)
        return file_list

    async def _get_video(self):
        if not self._is_dir and (await get_document_type(self.path))[0]:
            return self.path
        for dirpath, _, files in await sync_to_async(walk, self.path):
            for file in natsorted(files):
                file = ospath.join(dirpath, file)
                if (await get_document_type(file))[0]:
                    return file

    async def _final_path(self, outfile=''):
        if self._metadata:
            self._up_path = outfile or self.outfile
        else:
            scan_dir = self._up_path if self._is_dir else ospath.split(self._up_path)[0]
            for dirpath, _, files in await sync_to_async(walk, scan_dir):
                for file in files:
                    if file.endswith(tuple(self.listener.extensionFilter)):
                        await clean_target(ospath.join(dirpath, file))

            all_files = []
            for dirpath, _, files in await sync_to_async(walk, scan_dir):
                all_files.extend((dirpath, file) for file in files)
            if len(all_files) == 1:
                self._up_path = ospath.join(*all_files[0])

        return self._up_path

    async def _name_base_dir(self, path, info: str=None, multi: bool=False):
        base_dir, file_name = ospath.split(path)
        if not self.name or multi:
            if info:
                if await aiopath.isfile(path):
                    file_name = file_name.rsplit('.', 1)[0]
                file_name += f'_{info}.mkv'
            self.name = file_name
        if not self.name.upper().endswith(('MP4', 'MKV')):
            self.name += '.mkv'
        return base_dir if await aiopath.isfile(path) else path

    async def _run_cmd(self, cmd, status='prog'):
        await self._send_status(status)
        self.listener.suproc = await create_subprocess_exec(*cmd, stderr=PIPE)
        _, code = await gather(self.progress(status), self.listener.suproc.wait())
        if code == 0:
            if not self.listener.seed:
                await gather(*[clean_target(file) for file in self._files])
            self._files.clear()
            return True
        if self.listener.suproc == 'cancelled' or code == -9:
            self.is_cancel = True
        else:
            LOGGER.error('%s. Failed to %s: %s', (await self.listener.suproc.stderr.read()).decode().strip(), VID_MODE[self.mode], self.outfile)
            self._files.clear()

    async def _vid_extract(self):
        if file_list := await self._get_files():
            if self._metadata:
                base_dir = ospath.join(self.listener.dir, self.name.split('.', 1)[0])
                await makedirs(base_dir, exist_ok=True)
                streams = self._metadata[0]
            else:
                main_video = file_list[0]
                base_dir, (streams, _), self.size = await gather(self._name_base_dir(main_video, 'Extract', len(file_list) > 1),
                                                                 get_metavideo(main_video), get_path_size(main_video))
            self._start_handler(streams)
            await gather(self._send_status(), self.event.wait())
        else:
            return self._up_path

        await self._queue()
        if self.is_cancel:
            return
        if not self.data:
            return self._up_path

        if await aiopath.isfile(self._up_path) or self._metadata:
            base_name = self.name if self._metadata else ospath.basename(self.path)
            self._up_path = ospath.join(base_dir, f'{base_name.rsplit(".", 1)[0]} (EXTRACT)')
            await makedirs(self._up_path, exist_ok=True)
            base_dir = self._up_path

        task_files = []
        for file in file_list:
            self.path = file
            if not self._metadata:
                self.size = await get_path_size(self.path)
            base_name = self.name if self._metadata else ospath.basename(self.path)
            base_name = base_name.rsplit('.', 1)[0]
            extension = dict(zip(['audio', 'subtitle', 'video'], self.data['extension']))

            def _build_command(stream_data):
                cmd = [FFMPEG_NAME, '-hide_banner', '-ignore_unknown', '-i', self.path, '-map', f'0:{stream_data["map"]}']
                if self.data.get('alt_mode'):
                    if stream_data['type'] == 'audio':
                        cmd.extend(('-b:a', '156k'))
                    elif stream_data['type'] == 'video':
                        cmd.extend(('-c', 'copy'))
                else:
                    cmd.extend(('-c', 'copy'))
                cmd.extend((self.outfile, '-y'))
                return cmd

            keys = self.data['key']
            if isinstance(keys, int):
                stream_data = self.data['stream'][keys]
                self.name = f'{base_name}_{stream_data["lang"].upper()}.{extension[stream_data["type"]]}'
                self.outfile = ospath.join(base_dir, self.name)
                cmd = _build_command(stream_data)
                if await self._run_cmd(cmd):
                    task_files.append(file)
                else:
                    await move(file, self._up_path)
                if self.is_cancel:
                    return
            else:
                ext_all = []
                for stream_data in self.data['stream'].values():
                    for key in keys:
                        if key == stream_data['type']:
                            self.name = f'{base_name}_{stream_data["lang"].upper()}.{extension[key]}'
                            self.outfile = ospath.join(base_dir, self.name)
                            cmd = _build_command(stream_data)
                            if await self._run_cmd(cmd):
                                ext_all.append(file)
                            if self.is_cancel:
                                return
                if any(ext_all):
                    task_files.append(file)
                else:
                    await move(file, self._up_path)

        await gather(*[clean_target(file) for file in task_files])
        return await self._final_path(self._up_path)

    async def _vid_convert(self):
        file_list = await self._get_files()
        multi = len(file_list) > 1
        if not file_list:
            return self._up_path

        if self._metadata:
            base_dir = self.listener.dir
            await makedirs(base_dir, exist_ok=True)
            streams = self._metadata[0]
        else:
            main_video = file_list[0]
            base_dir, (streams, _), self.size = await gather(self._name_base_dir(main_video, 'Convert', len(file_list) > 1),
                                                             get_metavideo(main_video), get_path_size(main_video))
        self._start_handler(streams)
        await gather(self._send_status(), self.event.wait())
        await self._queue()
        if self.is_cancel:
            return
        if not self.data:
            return self._up_path
        self.outfile = self._up_path
        for file in file_list:
            self.path = file
            if not self._metadata:
                _, self.size = await gather(self._name_base_dir(self.path, f'Convert-{self.data}', multi), get_path_size(self.path))
            self.outfile = ospath.join(base_dir, self.name)
            self._files.append(self.path)
            cmd = [FFMPEG_NAME, '-hide_banner', '-ignore_unknown', '-y', '-i', self.path, '-map', '0:v:0',
                   '-vf', f'scale={self._qual[self.data]}:-2', '-map', '0:a:?', '-map', '0:s:?', '-c:a', 'copy', '-c:s', 'copy', self.outfile]
            await self._run_cmd(cmd)
            if self.is_cancel:
                return

        return await self._final_path()

    async def _rm_stream(self):
        file_list = await self._get_files()
        multi = len(file_list) > 1
        if not file_list:
            return self._up_path

        if self._metadata:
            base_dir = self.listener.dir
            await makedirs(base_dir, exist_ok=True)
            streams = self._metadata[0]
        else:
            main_video = file_list[0]
            base_dir, (streams, _), self.size = await gather(self._name_base_dir(main_video, 'Remove', multi),
                                                             get_metavideo(main_video), get_path_size(main_video))
        self._start_handler(streams)
        await gather(self._send_status(), self.event.wait())
        await self._queue()
        if self.is_cancel:
            return
        if not self.data:
            return self._up_path

        self.outfile = self._up_path
        for file in file_list:
            self.path = file
            if not self._metadata:
                _, self.size = await gather(self._name_base_dir(self.path, 'Remove', multi), get_path_size(self.path))
            key = self.data.get('key', '')
            self.outfile = ospath.join(base_dir, self.name)
            self._files.append(self.path)
            cmd = [FFMPEG_NAME, '-hide_banner', '-y', '-ignore_unknown', '-i', self.path]
            if key == 'audio':
                cmd.extend(('-map', '0', '-map', '-0:a'))
            elif key == 'subtitle':
                cmd.extend(('-map', '0', '-map', '-0:s'))
            else:
                for x in self.data['stream']:
                    if x not in self.data['sdata']:
                        cmd.extend(('-map', f'0:{x}'))
            cmd.extend(('-c', 'copy', self.outfile))
            await self._run_cmd(cmd)
            if self.is_cancel:
                return

        return await self._final_path()

    async def _vid_trimmer(self, start_time, end_time):
        await self._queue(True)
        if self.is_cancel:
            return
        self.outfile = self._up_path
        for file in (file_list := await self._get_files()):
            self.path = file
            if self._metadata:
                base_dir = self.listener.dir
                await makedirs(base_dir, exist_ok=True)
            else:
                base_dir, self.size = await gather(self._name_base_dir(self.path, 'Trim', len(file_list) > 1), get_path_size(self.path))
            self.outfile = ospath.join(base_dir, self.name)
            self._files.append(self.path)
            cmd = [FFMPEG_NAME, '-hide_banner', '-ignore_unknown', '-i', self.path, '-ss', start_time, '-to', end_time,
                   '-map', '0:v:0?', '-map', '0:a:?', '-map', '0:s:?', '-c:v', 'copy', '-c:a', 'copy', '-c:s', 'copy',  self.outfile, '-y']
            await self._run_cmd(cmd)
            if self.is_cancel:
                return

        return await self._final_path()

    async def _subsync(self, type: str='sync_manual'):
        if not self._is_dir:
            return self._up_path
        self.size = await get_path_size(self.path)
        list_files = natsorted(await listdir(self.path))
        if len(list_files) <= 1:
            return self._up_path
        sub_files, ref_files = [], []
        if type == 'sync_manual':
            index = 1
            self.data = {'list': {}, 'final': {}}
            for file in list_files:
                if (await get_document_type(ospath.join(self.path, file)))[0] or file.endswith(('.srt', '.ass')):
                    self.data['list'].update({index: file})
                    index += 1
            if not self.data['list']:
                return self._up_path
            self._start_handler()
            await gather(self._send_status(), self.event.wait())

            if self.is_cancel:
                return
            if not self.data or not self.data['final']:
                return self._up_path
            for key in self.data['final'].values():
                sub_files.append(ospath.join(self.path, key['file']))
                ref_files.append(ospath.join(self.path, key['ref']))
        else:
            for file in list_files:
                file_ = ospath.join(self.path, file)
                is_video, is_audio, _ = await get_document_type(file_)
                if is_video or is_audio:
                    ref_files.append(file_)
                elif file_.lower().endswith(('.srt', '.ass')):
                    sub_files.append(file_)

            if not sub_files:
                return self._up_path

            if not ref_files and len(sub_files) > 1:
                ref_files = list(filter(lambda x: (x, sub_files.remove(x)), sub_files))

            if not ref_files or not sub_files:
                return self._up_path

        for sub_file, ref_file in zip(sub_files, ref_files):
            self._files.extend((sub_file, ref_file))
            self.size = await get_path_size(ref_file)
            self.name = ospath.basename(sub_file)
            name, ext = ospath.splitext(sub_file)
            cmd = ['alass', '--allow-negative-timestamps', ref_file, sub_file, f'{name}_SYNC.{ext}']
            await self._run_cmd(cmd, 'direct')
            if self.is_cancel:
                return

        return await self._final_path(self._up_path)

    async def _vid_compress(self, quality=None):
        file_list = await self._get_files()
        multi = len(file_list) > 1
        if not file_list:
            return self._up_path

        if self._metadata:
            base_dir = self.listener.dir
            from aiofiles.os import makedirs
            await makedirs(base_dir, exist_ok=True)
            streams = self._metadata[0]
        else:
            main_video = file_list[0]
            from asyncio import gather
            from bot.helper.ext_utils.media_utils import get_metavideo
            from bot.helper.ext_utils.files_utils import get_path_size
            base_dir, (streams, _), self.size = await gather(self._name_base_dir(main_video, 'Compress', multi),
                                                             get_metavideo(main_video), get_path_size(main_video))
        self._start_handler(streams)
        from asyncio import gather
        await gather(self._send_status(), self.event.wait())
        await self._queue()
        if self.is_cancel:
            return
        if not isinstance(self.data, dict):
            return self._up_path

        self.outfile = self._up_path
        for file in file_list:
            self.path = file
            if not self._metadata:
                from asyncio import gather
                from bot.helper.ext_utils.files_utils import get_path_size
                _, self.size = await gather(self._name_base_dir(self.path, 'Compress', multi), get_path_size(self.path))
            self.outfile = ospath.join(base_dir, self.name)
            self._files.append(self.path)

            quality = self.data.get('quality', '720p')
            from bot import user_data
            user_id = self.listener.user_id
            user_dict = user_data.get(user_id, {})
            compress_dict = user_dict.get('compress_settings', {})
            if not compress_dict:
                compress_dict = {
                    '360p': {'vcodec': 'libx265', 'acodec': 'aac', 'crf': '24', 'res': '640x360', 'preset': 'slow', 'audio_b': '128k', 'bits': '8 bits'},
                    '480p': {'vcodec': 'libx265', 'acodec': 'aac', 'crf': '24', 'res': '854x480', 'preset': 'slow', 'audio_b': '128k', 'bits': '8 bits'},
                    '720p': {'vcodec': 'libx265', 'acodec': 'aac', 'crf': '24', 'res': '1280x720', 'preset': 'slow', 'audio_b': '192k', 'bits': '8 bits'},
                    '1080p': {'vcodec': 'libx265', 'acodec': 'aac', 'crf': '24', 'res': '1920x1080', 'preset': 'slow', 'audio_b': '192k', 'bits': '8 bits'}
                }

            settings = compress_dict.get(quality, compress_dict.get('720p', {}))
            vcodec = settings.get('vcodec', 'libx265')
            acodec = settings.get('acodec', 'aac')
            crf = settings.get('crf', '24')
            res = settings.get('res', '1280x720')
            preset = settings.get('preset', 'slow')
            audio_b = settings.get('audio_b', '192k')
            bits = settings.get('bits', '8 bits')
            pix_fmt = 'yuv420p10le' if '10' in bits else 'yuv420p'
            profile = 'main10' if '10' in bits else 'main'

            cmd = [FFMPEG_NAME, '-hide_banner', '-ignore_unknown', '-y', '-i', self.path, '-preset', preset, '-c:v', vcodec,
                   '-pix_fmt', pix_fmt, '-crf', crf, '-profile:v', profile, '-map', f'0:{self.data.get("video", 0)}', '-map', '0:s:?', '-c:s', 'copy']

            if 'audio' in self.data and self.data['audio'] != 0:
                cmd.extend(['-map', f'0:{self.data["audio"]}', '-c:a', acodec, '-b:a', audio_b])
            else:
                cmd.extend(['-c:a', acodec, '-b:a', audio_b])

            from bot import config_dict
            if banner := config_dict['COMPRESS_BANNER']:
                from aiofiles import open as aiopen
                sub_file = ospath.join(base_dir, 'subtitle.srt')
                self._files.append(sub_file)
                async with aiopen(sub_file, 'w') as f:
                    await f.write(f'1\n00:00:03,000 --> 00:00:08,000\n{banner}\n')
                cmd.extend(('-vf', f"subtitles='{sub_file}',scale={res},unsharp,eq=contrast=1.07", '-metadata', f'title={banner}', '-metadata:s:v',
                            f'title={banner}', '-x265-params', 'no-info=1', '-bsf:v', 'filter_units=remove_types=6'))
            else:
                cmd.extend(('-vf', f'scale={res}'))

            cmd.extend([self.outfile])
            await self._run_cmd(cmd, 'Compress')
            if self.is_cancel:
                return

        return await self._final_path()

    async def _subsync(self, type: str='sync_manual'):
        if not self._is_dir:
            return self._up_path
        self.size = await get_path_size(self.path)
        list_files = natsorted(await listdir(self.path))
        if len(list_files) <= 1:
            return self._up_path
        sub_files, ref_files = [], []
        if type == 'sync_manual':
            index = 1
            self.data = {'list': {}, 'final': {}}
            for file in list_files:
                if (await get_document_type(ospath.join(self.path, file)))[0] or file.endswith(('.srt', '.ass')):
                    self.data['list'].update({index: file})
                    index += 1
            if not self.data['list']:
                return self._up_path
            self._start_handler()
            await gather(self._send_status(), self.event.wait())

            if self.is_cancel:
                return
            if not self.data or not self.data['final']:
                return self._up_path
            for key in self.data['final'].values():
                sub_files.append(ospath.join(self.path, key['file']))
                ref_files.append(ospath.join(self.path, key['ref']))
        else:
            for file in list_files:
                file_ = ospath.join(self.path, file)
                is_video, is_audio, _ = await get_document_type(file_)
                if is_video or is_audio:
                    ref_files.append(file_)
                elif file_.lower().endswith(('.srt', '.ass')):
                    sub_files.append(file_)

            if not sub_files:
                return self._up_path

            if not ref_files and len(sub_files) > 1:
                ref_files = list(filter(lambda x: (x, sub_files.remove(x)), sub_files))

            if not ref_files or not sub_files:
                return self._up_path

        for sub_file, ref_file in zip(sub_files, ref_files):
            self._files.extend((sub_file, ref_file))
            self.size = await get_path_size(ref_file)
            self.name = ospath.basename(sub_file)
            name, ext = ospath.splitext(sub_file)
            cmd = ['alass', '--allow-negative-timestamps', ref_file, sub_file, f'{name}_SYNC.{ext}']
            await self._run_cmd(cmd, 'direct')
            if self.is_cancel:
                return

        return await self._final_path(self._up_path)

    async def _subsync(self, type: str='sync_manual'):
        if not self._is_dir:
            return self._up_path
        self.size = await get_path_size(self.path)
        list_files = natsorted(await listdir(self.path))
        if len(list_files) <= 1:
            return self._up_path
        sub_files, ref_files = [], []
        if type == 'sync_manual':
            index = 1
            self.data = {'list': {}, 'final': {}}
            for file in list_files:
                if (await get_document_type(ospath.join(self.path, file)))[0] or file.endswith(('.srt', '.ass')):
                    self.data['list'].update({index: file})
                    index += 1
            if not self.data['list']:
                return self._up_path
            self._start_handler()
            await gather(self._send_status(), self.event.wait())

            if self.is_cancel:
                return
            if not self.data or not self.data['final']:
                return self._up_path
            for key in self.data['final'].values():
                sub_files.append(ospath.join(self.path, key['file']))
                ref_files.append(ospath.join(self.path, key['ref']))
        else:
            for file in list_files:
                file_ = ospath.join(self.path, file)
                is_video, is_audio, _ = await get_document_type(file_)
                if is_video or is_audio:
                    ref_files.append(file_)
                elif file_.lower().endswith(('.srt', '.ass')):
                    sub_files.append(file_)

            if not sub_files:
                return self._up_path

            if not ref_files and len(sub_files) > 1:
                ref_files = list(filter(lambda x: (x, sub_files.remove(x)), sub_files))

            if not ref_files or not sub_files:
                return self._up_path

        for sub_file, ref_file in zip(sub_files, ref_files):
            self._files.extend((sub_file, ref_file))
            self.size = await get_path_size(ref_file)
            self.name = ospath.basename(sub_file)
            name, ext = ospath.splitext(sub_file)
            cmd = ['alass', '--allow-negative-timestamps', ref_file, sub_file, f'{name}_SYNC.{ext}']
            await self._run_cmd(cmd, 'direct')
            if self.is_cancel:
                return

        return await self._final_path(self._up_path)

    async def _subsync(self, type: str='sync_manual'):
        if not self._is_dir:
            return self._up_path
        self.size = await get_path_size(self.path)
        list_files = natsorted(await listdir(self.path))
        if len(list_files) <= 1:
            return self._up_path
        sub_files, ref_files = [], []
        if type == 'sync_manual':
            index = 1
            self.data = {'list': {}, 'final': {}}
            for file in list_files:
                if (await get_document_type(ospath.join(self.path, file)))[0] or file.endswith(('.srt', '.ass')):
                    self.data['list'].update({index: file})
                    index += 1
            if not self.data['list']:
                return self._up_path
            self._start_handler()
            await gather(self._send_status(), self.event.wait())

            if self.is_cancel:
                return
            if not self.data or not self.data['final']:
                return self._up_path
            for key in self.data['final'].values():
                sub_files.append(ospath.join(self.path, key['file']))
                ref_files.append(ospath.join(self.path, key['ref']))
        else:
            for file in list_files:
                file_ = ospath.join(self.path, file)
                is_video, is_audio, _ = await get_document_type(file_)
                if is_video or is_audio:
                    ref_files.append(file_)
                elif file_.lower().endswith(('.srt', '.ass')):
                    sub_files.append(file_)

            if not sub_files:
                return self._up_path

            if not ref_files and len(sub_files) > 1:
                ref_files = list(filter(lambda x: (x, sub_files.remove(x)), sub_files))

            if not ref_files or not sub_files:
                return self._up_path

        for sub_file, ref_file in zip(sub_files, ref_files):
            self._files.extend((sub_file, ref_file))
            self.size = await get_path_size(ref_file)
            self.name = ospath.basename(sub_file)
            name, ext = ospath.splitext(sub_file)
            cmd = ['alass', '--allow-negative-timestamps', ref_file, sub_file, f'{name}_SYNC.{ext}']
            await self._run_cmd(cmd, 'direct')
            if self.is_cancel:
                return

        return await self._final_path(self._up_path)

    async def _vid_marker(self, **kwargs):
        await self._queue(True)
        if self.is_cancel:
            return
        wmpath = ospath.join('watermark', f'{self.listener.mid}.png')
        for file in (file_list := await self._get_files()):
            self.path = file
            self._files.append(self.path)
            if self._metadata:
                base_dir, fsize = self.listener.dir, self.size
                await makedirs(base_dir, exist_ok=True)
            else:
                await self._name_base_dir(self.path, 'Marker', len(file_list) > 1)
                base_dir, fsize = await gather(self._name_base_dir(self.path, 'Marker', len(file_list) > 1), get_path_size(self.path))
            self.size = fsize + await get_path_size(wmpath)
            self.outfile = ospath.join(base_dir, self.name)
            wmsize, wmposition, popupwm = kwargs.get('wmsize'), kwargs.get('wmposition'), kwargs.get('popupwm') or ''
            if popupwm:
                duration = (await get_media_info(self.path))[0]
                popupwm = rf':enable=lt(mod(t\,{duration}/{popupwm})\,20)'

            hardusb, subfile = kwargs.get('hardsub') or '', kwargs.get('subfile', '')
            if hardusb and await aiopath.exists(subfile):
                fontname = kwargs.get('fontname', '').replace('_', ' ') or config_dict['HARDSUB_FONT_NAME']
                fontsize = f',FontSize={fontsize}' if (fontsize := kwargs.get('fontsize') or config_dict['HARDSUB_FONT_SIZE']) else ''
                fontcolour = f',PrimaryColour=&H{kwargs["fontcolour"]}' if kwargs.get('fontcolour') else ''
                boldstyle = ',Bold=1' if kwargs.get('boldstyle') else ''
                hardusb = f",subtitles='{subfile}':force_style='FontName={fontname},Shadow=1.5{fontsize}{fontcolour}{boldstyle}',unsharp,eq=contrast=1.07"

            quality = f',scale={self._qual[kwargs["quality"]]}:-2' if kwargs.get('quality') else ''
            cmd = [FFMPEG_NAME, '-hide_banner', '-ignore_unknown', '-y', '-i', self.path, '-i', wmpath, '-filter_complex',
                   f"[1][0]scale2ref=w='iw*{wmsize}/100':h='ow/mdar'[wm][vid];[vid][wm]overlay={wmposition}{popupwm}{quality}{hardusb}"]
            if config_dict['VIDTOOLS_FAST_MODE']:
                cmd.extend(('-c:v', 'libx264', '-preset', config_dict['LIB264_PRESET'], '-crf', '25'))
            cmd.extend(('-map', '0:a:?', '-map', '0:s:?', '-c:a', 'copy', '-c:s', 'copy', self.outfile))
            await self._run_cmd(cmd)
            if self.is_cancel:
                return
        await gather(clean_target(wmpath), clean_target(subfile))

        return await self._final_path()

    async def _merge_vids(self, **kwargs):
        list_files = []
        if self._is_dir:
            for dirpath, _, files in await sync_to_async(walk, self.path):
                if len(files) == 1 and not kwargs.get('vid_list'):
                    return self._up_path
                for file in natsorted(files):
                    video_file = ospath.join(dirpath, file)
                    if (await get_document_type(video_file))[0]:
                        self.size += await get_path_size(video_file)
                        safe_path = ospath.abspath(video_file).replace("'", r"\'")
                        list_files.append(f"file '{safe_path}'")
                        self._files.append(video_file)
        else:
            if not kwargs.get('vid_list'):
                return self._up_path
            if (await get_document_type(self.path))[0]:
                self.size += await get_path_size(self.path)
                safe_path = ospath.abspath(self.path).replace("'", r"\'")
                list_files.append(f"file '{safe_path}'")
                self._files.append(self.path)

        # Add interactive videos sent by user
        if vid_list := kwargs.get('vid_list'):
            for video_file in vid_list:
                if await aiopath.exists(video_file):
                    self.size += await get_path_size(video_file)
                    safe_path = ospath.abspath(video_file).replace("'", r"\'")
                    list_files.append(f"file '{safe_path}'")
                    self._files.append(video_file)

        self.outfile = self._up_path
        if len(list_files) > 1:
            base_dir = self.path if self._is_dir else ospath.dirname(self.path)
            await self._name_base_dir(self.path)
            await update_status_message(self.listener.message.chat.id)
            input_file = ospath.join(base_dir, 'input.txt')
            async with aiopen(input_file, 'w') as f:
                await f.write('\n'.join(list_files))

            self.outfile = ospath.join(base_dir, self.name)
            temp_outfile = ospath.join(base_dir, f"temp_{self.name}")
            cmd = [FFMPEG_NAME, '-ignore_unknown', '-f', 'concat', '-safe', '0', '-i', input_file, '-map', '0', '-c', 'copy', temp_outfile, '-y']
            await self._run_cmd(cmd, 'direct')
            await clean_target(input_file)

            if not self.is_cancel and await aiopath.exists(temp_outfile):
                await move(temp_outfile, self.outfile)

            # Clean up user-sent videos after merge
            if vid_list:
                await gather(*[clean_target(v) for v in vid_list])
                vid_dir = ospath.join('vid_vid', str(self.listener.mid))
                if await aiopath.exists(vid_dir):
                    await clean_target(vid_dir)

            if self.is_cancel:
                return

        return await self._final_path()

    async def _merge_auds(self, **kwargs):
        main_video = False
        if self._is_dir:
            for dirpath, _, files in await sync_to_async(walk, self.path):
                if len(files) == 1 and not kwargs.get('vid_list'):
                    return self._up_path
                for file in natsorted(files):
                    file = ospath.join(dirpath, file)
                    is_video, is_audio, _ = await get_document_type(file)
                    if is_video:
                        if main_video:
                            continue
                        main_video = file
                    if is_audio:
                        self.size += await get_path_size(file)
                        self._files.append(file)
        else:
            if not kwargs.get('vid_list'):
                return self._up_path
            is_video, is_audio, _ = await get_document_type(self.path)
            if is_video:
                main_video = self.path
            elif is_audio:
                self.size += await get_path_size(self.path)
                self._files.append(self.path)

        # Add interactive audio/video files sent by user
        if vid_list := kwargs.get('vid_list'):
            for media_file in vid_list:
                if await aiopath.exists(media_file):
                    is_video, is_audio, _ = await get_document_type(media_file)
                    if is_video and not main_video:
                        main_video = media_file
                    elif is_audio:
                        self.size += await get_path_size(media_file)
                        self._files.append(ospath.abspath(media_file))

        self._files.insert(0, main_video)
        self.outfile = self._up_path
        if len(self._files) > 1 and main_video:
            _, size = await gather(self._name_base_dir(self.path), get_path_size(main_video))
            self.size += size
            await update_status_message(self.listener.message.chat.id)
            cmd = [FFMPEG_NAME, '-hide_banner', '-ignore_unknown']
            for i in self._files:
                cmd.extend(('-i', i))
            cmd.extend(('-map', '0:v:0?', '-map', '0:a:?'))
            for j in range(1, len(self._files)):
                cmd.extend(('-map', f'{j}:a'))

            base_dir = self.path if self._is_dir else ospath.dirname(self.path)
            self.outfile = ospath.join(base_dir, self.name)
            temp_outfile = ospath.join(base_dir, f"temp_{self.name}")
            streams = (await get_metavideo(main_video))[0]
            audio_track = len([1+i for i in range(len(streams)) if streams[i].get('codec_type') == 'audio'])
            new_track_idx = audio_track if audio_track == 0 else audio_track + 1
            cmd.extend((f'-disposition:a:{new_track_idx}', 'default', '-map',
                        '0:s:?', '-c:v', 'copy', '-c:a', 'copy', '-c:s',
                        'copy', temp_outfile, '-y'))
            await self._run_cmd(cmd, 'direct')

            if not self.is_cancel and await aiopath.exists(temp_outfile):
                await move(temp_outfile, self.outfile)

            if vid_list:
                await gather(*[clean_target(v) for v in vid_list])
                vid_dir = ospath.join('vid_vid', str(self.listener.mid))
                if await aiopath.exists(vid_dir):
                    await clean_target(vid_dir)

            if self.is_cancel:
                return

        return await self._final_path()

    async def _merge_subs(self, **kwargs):
        main_video = False
        if self._is_dir:
            for dirpath, _, files in await sync_to_async(walk, self.path):
                if len(files) == 1 and not kwargs.get('vid_list'):
                    return self._up_path
                for file in natsorted(files):
                    file = ospath.join(dirpath, file)
                    is_video, is_sub = (await get_document_type(file))[0], file.endswith(('.ass', '.srt', '.vtt'))
                    if is_video:
                        if main_video:
                            continue
                        main_video = file
                    if is_sub:
                        self.size += await get_path_size(file)
                        self._files.append(file)
        else:
            if not kwargs.get('vid_list'):
                return self._up_path
            is_video, is_sub = (await get_document_type(self.path))[0], self.path.endswith(('.ass', '.srt', '.vtt'))
            if is_video:
                main_video = self.path
            elif is_sub:
                self.size += await get_path_size(self.path)
                self._files.append(self.path)

        # Add interactive sub/video files sent by user
        if vid_list := kwargs.get('vid_list'):
            for media_file in vid_list:
                if await aiopath.exists(media_file):
                    is_video, is_sub = (await get_document_type(media_file))[0], media_file.endswith(('.ass', '.srt', '.vtt'))
                    if is_video and not main_video:
                        main_video = media_file
                    elif is_sub:
                        self.size += await get_path_size(media_file)
                        self._files.append(ospath.abspath(media_file))

        self._files.insert(0, main_video)
        self.outfile = self._up_path
        if len(self._files) > 1 and main_video:
            base_dir = self.path if self._is_dir else ospath.dirname(self.path)
            _, size = await gather(self._name_base_dir(self.path), get_path_size(main_video))
            self.size += size
            cmd = [FFMPEG_NAME, '-hide_banner', '-ignore_unknown', '-y']
            self.outfile, status = ospath.join(base_dir, self.name), 'direct'
            temp_outfile = ospath.join(base_dir, f"temp_{self.name}")
            if kwargs.get('hardsub'):
                self.path, status = self._files[0], 'prog'
                cmd.extend(('-i', self.path, '-vf'))
                fontname = kwargs.get('fontname', '').replace('_', ' ') or config_dict['HARDSUB_FONT_NAME']
                fontsize = f',FontSize={fontsize}' if (fontsize := kwargs.get('fontsize') or config_dict['HARDSUB_FONT_SIZE']) else ''
                fontcolour = f',PrimaryColour=&H{kwargs["fontcolour"]}' if kwargs.get('fontcolour') else ''
                boldstyle = ',Bold=1' if kwargs.get('boldstyle') else ''
                quality = f',scale={self._qual[kwargs["quality"]]}:-2' if kwargs.get('quality') else ''

                sub_file = self._files[1].replace("\\", "\\\\").replace(":", "\\:")
                cmd.append(f"subtitles='{sub_file}':force_style='FontName="
                           f"{fontname},Shadow=1.5{fontsize}{fontcolour}"
                           f"{boldstyle}'{quality},unsharp,eq=contrast=1.07")

                if config_dict['VIDTOOLS_FAST_MODE']:
                    cmd.extend(('-preset', config_dict['LIB264_PRESET'], '-c:v', 'libx264', '-crf', '24'))
                    extra = ['-map', '0:a:?', '-c:a', 'copy']
                else:
                    cmd.extend(('-preset', config_dict['LIB265_PRESET'], '-c:v', 'libx265', '-pix_fmt', 'yuv420p10le', '-crf', '24',
                                '-profile:v', 'main10', '-x265-params', 'no-info=1', '-bsf:v', 'filter_units=remove_types=6'))
                    extra = ['-c:a', 'aac', '-b:a', '160k', '-map', '0:1']
                cmd.extend(['-map', '0:v:0?', '-map', '-0:s'] + extra + [temp_outfile])
            else:
                for i in self._files:
                    cmd.extend(('-i', i))
                cmd.extend(('-map', '0:v:0?', '-map', '0:a:?', '-map', '0:s:?'))
                for j in range(1, (len(self._files))):
                    cmd.extend(('-map', f'{j}:s'))
                cmd.extend(('-c:v', 'copy', '-c:a', 'copy', '-c:s', 'srt', temp_outfile))
            await self._run_cmd(cmd, status)

            if not self.is_cancel and await aiopath.exists(temp_outfile):
                await move(temp_outfile, self.outfile)

            # Clean up user-sent media after merge
            if vid_list := kwargs.get('vid_list'):
                await gather(*[clean_target(v) for v in vid_list])
                vid_dir = ospath.join('vid_vid', str(self.listener.mid))
                if await aiopath.exists(vid_dir):
                    await clean_target(vid_dir)

            if self.is_cancel:
                return

        return await self._final_path()

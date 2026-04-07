import asyncio
from secrets import token_hex
import os
from bot import LOGGER, task_dict, task_dict_lock
from bot.helper.ext_utils.bot_utils import sync_to_async
from bot.helper.mirror_utils.status_utils.mega_status import MegaDownloadStatus
from bot.helper.mirror_utils.status_utils.queue_status import QueueStatus
from bot.helper.ext_utils.status_utils import MirrorStatus
from bot.helper.telegram_helper.message_utils import sendStatusMessage
from bot.helper.ext_utils.task_manager import check_limits_size, check_running_tasks, stop_duplicate_check
from mega import Mega

mega_tasks = {}

class MegaAppListener:
    def __init__(self, listener):
        self.listener = listener
        self.mega = None
        self.mega_client = None
        self.gid = token_hex(5)
        self.mega_status = None
        self.name = ""
        self.size = 0
        self.temp_path = f"/usr/src/app/downloads/{self.gid}"
        self.is_cancelled = False
        mega_tasks[self.gid] = self.temp_path

    async def get_metadata(self):
        try:
            self.mega = Mega()
            self.mega_client = await sync_to_async(self.mega.login)
            info = await sync_to_async(self.mega_client.get_public_url_info, self.listener.link)
            if not info or 'size' not in info:
                return False
            self.size = info.get('size', 0)
            self.name = info.get('name', 'Mega_Download')
            self.listener.size = self.size
            self.listener.name = self.name
            return True
        except Exception as e:
            LOGGER.error(f"Mega Metadata Error: {e}")
            return False

    async def _install_megacmd(self):
        script = '''
        if ! command -v mega-cmd &> /dev/null; then
            export DEBIAN_FRONTEND=noninteractive
            wget -q https://mega.nz/linux/repo/xUbuntu_22.04/amd64/megacmd-xUbuntu_22.04_amd64.deb
            apt-get install -y ./megacmd-xUbuntu_22.04_amd64.deb
            rm ./megacmd-xUbuntu_22.04_amd64.deb
        fi
        '''
        import subprocess as py_subprocess
        try:
            py_subprocess.run(["bash", "-c", script], check=False, capture_output=True)
            return True
        except:
            pass
        return False

    async def download(self, path):
        await self._install_megacmd()

        if not await self.get_metadata():
            await self.listener.onDownloadError("Failed to extract Mega Metadata.")
            return

        msg, button = await stop_duplicate_check(self.listener)
        if msg:
            await self.listener.onDownloadError(msg, button)
            return

        limit_exc = await check_limits_size(self.listener, self.size)
        if limit_exc:
            await self.listener.onDownloadError(limit_exc)
            return

        t_mid = self.listener.mid
        added_to_queue, event = await check_running_tasks(t_mid)
        if added_to_queue:
            async with task_dict_lock:
                task_dict[self.listener.mid] = QueueStatus(
                    self.listener, self.size, self.gid, "dl"
                )
            await self.listener.onDownloadStart()
            if self.listener.multi <= 1:
                await sendStatusMessage(self.listener.message)
            await event.wait()
            if getattr(self.listener, 'is_cancelled', False):
                return

        self.mega_status = MegaDownloadStatus(
            self.listener, self, self.gid, MirrorStatus.STATUS_DOWNLOADING
        )
        async with task_dict_lock:
            task_dict[self.listener.mid] = self.mega_status

        await self.listener.onDownloadStart()
        if self.listener.multi <= 1:
            await sendStatusMessage(self.listener.message)

        os.makedirs(path, exist_ok=True)
        self.temp_path = path

        async def track_disk_progress():
            while not getattr(self.listener, 'is_cancelled', False):
                try:
                    total_bytes = sum(os.path.getsize(os.path.join(root, file)) for root, _, files in os.walk(path) for file in files)
                    self.mega_status._downloaded_bytes = total_bytes
                except Exception:
                    pass
                await asyncio.sleep(2)

        progress_task = asyncio.create_task(track_disk_progress())

        try:
            # We'll use mega-get (MEGAcmd) which is parallel and blazing fast.
            # If it fails, fallback to mega.py python module.
            import subprocess
            cmd = ["mega-get", self.listener.link, path]
            process = await asyncio.create_subprocess_exec(*cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

            await process.wait()
            progress_task.cancel()

            if process.returncode == 0:
                await self.cleanup()
                await self.listener.onDownloadComplete()
                return
            else:
                LOGGER.info("mega-get failed. Falling back to mega.py")
                # Fallback to pure python mega API
                progress_task = asyncio.create_task(track_disk_progress())
                await sync_to_async(self.mega_client.download_url, self.listener.link, dest_path=path)
                progress_task.cancel()

                await self.cleanup()
                await self.listener.onDownloadComplete()
                return

        except Exception as e:
            progress_task.cancel()
            if getattr(self.listener, 'is_cancelled', False):
                return
            await self.listener.onDownloadError(f"Mega Download Error: {e}")
        finally:
            await self.cleanup()

    async def cleanup(self):
        try:
            if self.gid in mega_tasks:
                del mega_tasks[self.gid]
        except:
            pass

    async def cancel_task(self):
        self.listener.is_cancelled = True
        try:
            import subprocess
            subprocess.run(["pkill", "-f", "mega-get"])
        except:
            pass
        await self.cleanup()

import asyncio
from secrets import token_hex
import os
import re
from bot import LOGGER, task_dict, task_dict_lock
from bot.helper.ext_utils.bot_utils import sync_to_async
from bot.helper.mirror_utils.status_utils.mega_status import MegaDownloadStatus
from bot.helper.mirror_utils.status_utils.queue_status import QueueStatus
from bot.helper.ext_utils.status_utils import MirrorStatus
from bot.helper.telegram_helper.message_utils import sendStatusMessage
from bot.helper.ext_utils.task_manager import check_limits_size, check_running_tasks, stop_duplicate_check

mega_tasks = {}

class MegaAppListener:
    def __init__(self, listener):
        self.listener = listener
        self.gid = token_hex(5)
        self.mega_status = None
        self.name = ""
        self.size = 0
        self.temp_path = f"/usr/src/app/downloads/{self.gid}"
        self.is_cancelled = False
        mega_tasks[self.gid] = self.temp_path

    async def get_metadata(self):
        try:
            import subprocess

            # Since VPS containers might lack sudo permissions for APT-GET,
            # we must fallback to JD dynamically if neither mega-get nor megadl is successfully verified inside PATH.
            if not await self._install_megatools():
                LOGGER.info("megadl missing from PATH. Bypassing metadata.")
                return False

            cmd = ["megadl", "--print-urls", self.listener.link]
            process = await asyncio.create_subprocess_exec(*cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = await process.communicate()
            if process.returncode != 0:
                LOGGER.error(f"Mega Metadata Error: {stderr.decode().strip()}")
                return False

            output = stdout.decode().strip()
            self.name = f"Mega_Download_{self.gid}"
            self.size = 0

            self.listener.name = self.name
            self.listener.size = self.size
            return True
        except Exception as e:
            LOGGER.error(f"Mega Metadata Error: {e}")
            return False

    async def _install_megatools(self):
        import shutil
        if shutil.which('megadl'):
            return True
        script = '''
        if ! command -v megadl &> /dev/null; then
            export DEBIAN_FRONTEND=noninteractive
            apt-get update -y || true
            apt-get install -y megatools || true
        fi
        '''
        import subprocess as py_subprocess
        try:
            py_subprocess.run(["bash", "-c", script], check=False, capture_output=True)
            if shutil.which('megadl'):
                return True
        except:
            pass
        return False

    async def _install_megacmd(self):
        import shutil
        if shutil.which('mega-get'):
            return True
        script = '''
        if ! command -v mega-cmd &> /dev/null; then
            export DEBIAN_FRONTEND=noninteractive
            wget -q https://mega.nz/linux/repo/xUbuntu_22.04/amd64/megacmd-xUbuntu_22.04_amd64.deb
            apt-get install -y ./megacmd-xUbuntu_22.04_amd64.deb || true
            rm ./megacmd-xUbuntu_22.04_amd64.deb
        fi
        '''
        import subprocess as py_subprocess
        try:
            py_subprocess.run(["bash", "-c", script], check=False, capture_output=True)
            if shutil.which('mega-get'):
                return True
        except:
            pass
        return False

    async def download(self, path):
        await self._install_megacmd()

        # If metadata extraction fails entirely (e.g. megadl is missing due to permission denial), we immediately fallback to JDownloader
        if not await self.get_metadata():
            LOGGER.info("Mega CLI failed or metadata could not be extracted. Delegating direct to JDownloader.")
            from bot.helper.mirror_utils.download_utils.jd_download import add_jd_download
            self.listener.isJd = True
            try:
                await add_jd_download(self.listener, path)
            except Exception as e:
                LOGGER.error(f"Fallback JDownloader failed: {e}")
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
                    if self.listener.size == 0 and total_bytes > 0:
                        self.listener.size = total_bytes * 2 # Estimation buffer
                except Exception:
                    pass
                await asyncio.sleep(2)

        progress_task = asyncio.create_task(track_disk_progress())

        try:
            import subprocess
            import shutil

            if shutil.which('mega-get'):
                cmd = ["mega-get", self.listener.link, path]
            else:
                cmd = ["megadl", "--path", path, self.listener.link]

            process = await asyncio.create_subprocess_exec(*cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

            await process.wait()
            progress_task.cancel()

            if process.returncode == 0:
                await self.cleanup()
                await self.listener.onDownloadComplete()
                return
            else:
                LOGGER.info("Mega CLI failed. Fallback to JDownloader for Mega link.")
                from bot.helper.mirror_utils.download_utils.jd_download import add_jd_download
                self.listener.isJd = True
                try:
                    await add_jd_download(self.listener, path)
                except Exception as e:
                    LOGGER.error(f"Fallback JDownloader failed: {e}")

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
            subprocess.run(["pkill", "-f", "megadl"])
        except:
            pass
        await self.cleanup()

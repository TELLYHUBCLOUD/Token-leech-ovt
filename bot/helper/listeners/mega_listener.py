import asyncio
import os
import shutil
import re
from time import time
from secrets import token_hex
from aiofiles.os import makedirs, path as aiopath
from asyncio import create_subprocess_exec, wait_for
from asyncio.subprocess import PIPE, STDOUT
import subprocess as py_subprocess

from bot import LOGGER, task_dict, task_dict_lock, config_dict
from bot.helper.ext_utils.status_utils import MirrorStatus
from bot.helper.ext_utils.bot_utils import cmd_exec, sync_to_async
from bot.helper.ext_utils.task_manager import (
    check_running_tasks,
    stop_duplicate_check,
    check_limits_size,
)
from bot.helper.mirror_utils.status_utils.mega_status import MegaDownloadStatus
from bot.helper.mirror_utils.status_utils.queue_status import QueueStatus
from bot.helper.telegram_helper.message_utils import sendStatusMessage

try:
    from mega import Mega
except ImportError:
    Mega = None


mega_tasks = {}

class MegaAppListener:
    def __init__(self, listener):
        self.listener = listener
        self.process = None
        self.gid = token_hex(5)
        self.mega_status = None
        self.name = ""
        self.size = 0
        self.temp_path = f"/usr/src/app/downloads/{self.gid}"
        self._is_cleaned = False
        self._last_time = time()
        self._val_last = 0
        mega_tasks[self.gid] = self.temp_path

    async def cleanup(self):
        if getattr(self.listener, 'is_cancelled', False):
            return
        self._is_cleaned = True
        try:
            if self.gid in mega_tasks:
                del mega_tasks[self.gid]
        except Exception as e:
            pass

    def _install_megatools(self):
        if shutil.which('megadl'):
            return True
        LOGGER.info("megatools not found, installing on the fly...")
        script = '''
        SUDO=""
        if command -v sudo >/dev/null 2>&1; then
            if sudo -n true 2>/dev/null; then
                SUDO="sudo"
            fi
        fi
        export DEBIAN_FRONTEND=noninteractive
        $SUDO apt-get update -y || true
        $SUDO apt-get install -y megatools
        '''
        try:
            if os.geteuid() != 0 and not shutil.which('sudo'):
                # Bypass script execution safely if absolutely zero privileges are available
                LOGGER.info("Insufficient permissions to run apt-get. Falling back to native PyMega...")
                return False
            py_subprocess.run(["bash", "-c", script], check=True, capture_output=True, text=True)
            return True
        except py_subprocess.CalledProcessError as e:
            LOGGER.error(f"Failed to install megatools: {e.stdout}\n{e.stderr}")
            return False
        except Exception as e:
            LOGGER.error(f"Failed to install megatools: {e}")
            return False

    async def get_metadata(self):
        global Mega
        if not Mega:
            LOGGER.info("mega.py module missing. Installing on the fly...")
            try:
                py_subprocess.run(["pip3", "install", "mega.py", "--upgrade"], check=True, capture_output=True)
                from mega import Mega
            except Exception as e:
                LOGGER.error(f"Failed to install mega.py: {e}")
                return False

        try:
            mega = Mega()
            # Attempt anonymous login to bypass rate limits or just anonymous state
            m = await sync_to_async(mega.login)

            # Fetch metadata
            info = await sync_to_async(m.get_public_url_info, self.listener.link)
            if not info or 'size' not in info:
                LOGGER.error("Failed to extract Mega metadata.")
                return False

            self.size = info.get('size', 0)
            self.name = info.get('name', 'Mega_Download')
            self.listener.size = self.size
            self.listener.name = self.name
            return True
        except Exception as e:
            LOGGER.error(f"Mega Metadata Error: {e}")
            return False

    async def download(self, path):
        self.use_mega_py = False
        try:
            if not self._install_megatools():
                LOGGER.info("megatools installation failed. Falling back to native mega.py...")
                self.use_mega_py = True

            if not await self.get_metadata():
                # If metadata fails (e.g. folder links via mega.py failing), fallback to JDownloader
                return False

        except Exception as setup_err:
            LOGGER.error(f"Mega Setup Error: {setup_err}")
            return False

        try:
            msg, button = await stop_duplicate_check(self.listener)
            if msg:
                await self.listener.onDownloadError(msg, button)
                return True

            limit_exc = await check_limits_size(self.listener, self.size)
            if limit_exc:
                await self.listener.onDownloadError(limit_exc)
                return True

            t_mid = self.listener.mid
            added_to_queue, event = await check_running_tasks(t_mid)
            if added_to_queue:
                LOGGER.info(f"Added to Queue/Download: {self.name}")
                async with task_dict_lock:
                    task_dict[self.listener.mid] = QueueStatus(
                        self.listener, self.size, self.gid, "dl"
                    )
                await self.listener.onDownloadStart()
                if self.listener.multi <= 1:
                    await sendStatusMessage(self.listener.message)
                await event.wait()
                if getattr(self.listener, 'is_cancelled', False):
                    return True

            self.mega_status = MegaDownloadStatus(
                self.listener, self, self.gid, MirrorStatus.STATUS_DOWNLOADING
            )
            async with task_dict_lock:
                task_dict[self.listener.mid] = self.mega_status

            if added_to_queue:
                LOGGER.info(f"Start Queued Download from Mega: {self.name}")
            else:
                LOGGER.info(f"Download from Mega: {self.name}")
                await self.listener.onDownloadStart()
                if self.listener.multi <= 1:
                    await sendStatusMessage(self.listener.message)

            await makedirs(path, exist_ok=True)
            self.temp_path = path

            # Polling task for disk size instead of regex output parsing
            async def track_disk_progress():
                while True:
                    if self.process is not None and self.process.returncode is not None:
                        break
                    if getattr(self.listener, 'is_cancelled', False):
                        break
                    try:
                        total_bytes = 0
                        for dirpath, _, filenames in os.walk(path):
                            for f in filenames:
                                fp = os.path.join(dirpath, f)
                                if not os.path.islink(fp):
                                    total_bytes += os.path.getsize(fp)

                        self.mega_status._downloaded_bytes = total_bytes
                        cur_time = time()
                        if cur_time - self._last_time >= 2:
                            speed = int((total_bytes - self._val_last) / (cur_time - self._last_time))
                            # Prevent negative spikes
                            self.mega_status._speed = speed if speed > 0 else 0
                            self._val_last = total_bytes
                            self._last_time = cur_time
                    except Exception:
                        pass
                    await asyncio.sleep(2)

            if self.use_mega_py:
                progress_task = asyncio.create_task(track_disk_progress())
                try:
                    mega = Mega()
                    m = await sync_to_async(mega.login)
                    await sync_to_async(m.download_url, self.listener.link, dest_path=path, dest_filename=self.name)
                    progress_task.cancel()
                    if getattr(self.listener, 'is_cancelled', False):
                        return True
                    await self.cleanup()
                    await self.listener.onDownloadComplete()
                    return True
                except Exception as py_err:
                    progress_task.cancel()
                    if getattr(self.listener, 'is_cancelled', False):
                        return True
                    LOGGER.error(f"mega.py download failed: {py_err}")
                    return False

            # Download using megadl
            command = ["megadl", "--path", path, self.listener.link]

            self.process = await create_subprocess_exec(
                *command,
                stdout=PIPE,
                stderr=STDOUT,
            )

            progress_task = asyncio.create_task(track_disk_progress())
            await self.process.wait()
            progress_task.cancel()

            if self.process.returncode == 0:
                await self.cleanup()
                await self.listener.onDownloadComplete()
                return True
            else:
                if getattr(self.listener, 'is_cancelled', False):
                    return True

                # Check output for errors
                stdout_data = ""
                if self.process.stdout:
                    stdout_data = (await self.process.stdout.read()).decode().strip()

                if self.process.returncode != -9:
                    err_msg = f"megadl failed with exit code {self.process.returncode}\n{stdout_data}"
                    LOGGER.error(err_msg)
                    # Force JDownloader fallback for failed execution by returning False to mega_download.py
                    return False
                return True
        except Exception as e:
            if getattr(self.listener, 'is_cancelled', False):
                return True
            LOGGER.error(f"Mega Download Logic Error: {e}")
            await self.listener.onDownloadError(str(e))
            return True
        finally:
            await self.cleanup()

    async def cancel_task(self):
        self.listener.is_cancelled = True
        if self.process is not None:
            try:
                self.process.kill()
            except Exception:
                pass
        LOGGER.info(f"Mega Task Cancelled: {self.name}")
        await self.cleanup()

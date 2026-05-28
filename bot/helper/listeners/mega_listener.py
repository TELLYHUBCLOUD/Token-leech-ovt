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
        self.is_folder = False
        mega_tasks[self.gid] = self.temp_path

    async def get_metadata(self):
        try:
            import subprocess
            if not await self._install_megatools():
                LOGGER.info("megatools missing from PATH. Bypassing metadata.")
                return False

            cmd = ["megals", "-l", "--header", self.listener.link]
            process = await asyncio.create_subprocess_exec(*cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = await process.communicate()

            output = stdout.decode().strip()
            if process.returncode != 0 and not output:
                LOGGER.error(f"Mega Metadata Error: {stderr.decode().strip()}")
                return False

            lines = output.split('\n')
            total_size = 0
            name = None

            if "folder/" in self.listener.link or "#F!" in self.listener.link:
                self.is_folder = True

            if len(lines) > 2:
                for line in lines[2:]:
                    parts = line.strip().split(maxsplit=1)
                    if len(parts) == 2 and parts[0].isdigit():
                        total_size += int(parts[0])
                        if not name:
                            match = re.search(r"\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\s+(.*)", parts[1])
                            if match:
                                extracted = match.group(1)
                                name = extracted.split('/')[0] if '/' in extracted else extracted
                            else:
                                name = parts[1].split()[-1].split('/')[0]

            self.name = name if name else f"Mega_Download_{self.gid}"
            self.size = total_size

            self.listener.name = self.name
            self.listener.size = self.size

            if total_size == 0 and self.is_folder:
                await self.listener.onDownloadError("Mega Folder is empty or invalid link.")
                return False

            return True
        except Exception as e:
            LOGGER.error(f"Mega Metadata Error: {e}")
            return False

    async def _install_megatools(self):
        import shutil
        if shutil.which('megadl') and shutil.which('megals'):
            return True

        script = '''
        if ! command -v megadl &> /dev/null; then
            export DEBIAN_FRONTEND=noninteractive
            if command -v apt-get &> /dev/null; then
                apt-get update -y || true
                apt-get install -y megatools || true
            elif command -v apk &> /dev/null; then
                apk add megatools || true
            fi
        fi
        '''
        import subprocess as py_subprocess
        try:
            process = await asyncio.create_subprocess_exec("bash", "-c", script, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            await process.wait()
            if shutil.which('megadl') and shutil.which('megals'):
                return True
        except:
            pass
        return False

    async def download(self, path):
        import shutil
        if not shutil.which('megadl') or not shutil.which('megals'):
            if not await self._install_megatools():
                await self.listener.onDownloadError("❌ MEGA download failed: megatools not installed on server. Contact bot owner.")
                return

        if not await self.get_metadata():
            await self.listener.onDownloadError("Invalid MEGA link or metadata extraction failed.")
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
                    total_bytes = await sync_to_async(self._get_folder_size, path)
                    self.mega_status._downloaded_bytes = total_bytes
                    if self.listener.size == 0 and total_bytes > 0:
                        self.listener.size = total_bytes * 2
                except Exception:
                    pass
                await asyncio.sleep(2)

        progress_task = asyncio.create_task(track_disk_progress())

        try:
            import subprocess
            cmd = ["megadl", "--path", path, self.listener.link]
            process = await asyncio.create_subprocess_exec(*cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            stdout, stderr = await process.communicate()
            progress_task.cancel()

            if process.returncode == 0:
                await self.cleanup()
                await self.listener.onDownloadComplete()
                return
            else:
                error_out = stderr.decode().lower()
                if "bandwidth limit" in error_out or "quota" in error_out:
                    await self.listener.onDownloadError("Mega Download Error: Quota exceeded.")
                elif "invalid" in error_out or "link" in error_out or "error" in error_out:
                    await self.listener.onDownloadError(f"Mega Download Error: Invalid link or file not found. Output: {error_out[:100]}")
                else:
                    await self.listener.onDownloadError(f"Mega Download Error: process failed. Output: {error_out[:100]}")

        except Exception as e:
            progress_task.cancel()
            if getattr(self.listener, 'is_cancelled', False):
                return
            await self.listener.onDownloadError(f"Mega Download Error: {e}")
        finally:
            await self.cleanup()

    def _get_folder_size(self, folder):
        total = 0
        for root, _, files in os.walk(folder):
            for file in files:
                total += os.path.getsize(os.path.join(root, file))
        return total

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
            subprocess.run(["pkill", "-f", "megadl"])
        except:
            pass
        await self.cleanup()

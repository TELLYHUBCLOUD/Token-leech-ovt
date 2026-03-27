from time import time
from secrets import token_hex
from aiofiles.os import makedirs
from asyncio import create_subprocess_exec, wait_for
from asyncio import subprocess as asynciosubprocess
import shutil
import subprocess as py_subprocess
from re import search as re_search
from contextlib import suppress

from bot import LOGGER, task_dict, task_dict_lock, config_dict
from bot.helper.ext_utils.status_utils import MirrorStatus
from bot.helper.ext_utils.bot_utils import cmd_exec
from bot.helper.ext_utils.task_manager import (
    check_running_tasks,
    stop_duplicate_check,
    check_limits_size,
)
from bot.helper.mirror_utils.status_utils.mega_status import MegaDownloadStatus
from bot.helper.mirror_utils.status_utils.queue_status import QueueStatus
from bot.helper.telegram_helper.message_utils import sendStatusMessage

mega_tasks = {}


async def mega_cleanup():
    if not mega_tasks:
        return
    LOGGER.info("Running Mega Cleanup...")
    for path in list(mega_tasks.values()):
        try:
            await cmd_exec(["mega-rm", "-r", "-f", path])
        except Exception as e:
            LOGGER.error(f"Mega Restart Cleanup Failed for {path}: {e}")
    mega_tasks.clear()


class MegaAppListener:
    def __init__(self, listener):
        self.listener = listener
        self.process = None
        self.gid = token_hex(5)
        self.mega_status = None
        self.name = ""
        self.size = 0
        self.temp_path = f"/wzml_{self.gid}"
        self.mega_tags = set()
        self._is_cleaned = False
        self._last_time = time()
        self._val_last = 0
        mega_tasks[self.gid] = self.temp_path

    async def login(self):
        MEGA_EMAIL = config_dict.get('MEGA_EMAIL', '')
        MEGA_PASSWORD = config_dict.get('MEGA_PASSWORD', '')
        if MEGA_EMAIL and MEGA_PASSWORD:
            try:
                await cmd_exec(["mega-login", MEGA_EMAIL, MEGA_PASSWORD])
            except Exception as e:
                raise Exception(f"Mega Login Failed: {e}")
        else:
            pass

    async def create_temp_path(self):
        await cmd_exec(["mega-mkdir", self.temp_path])

    async def import_link(self):
        stdout, stderr, ret = await cmd_exec(
            ["mega-import", self.listener.link, self.temp_path]
        )
        if ret != 0:
            raise Exception(f"Mega Import Failed: {stderr}")

    async def get_metadata_and_target(self):
        stdout, _, ret = await cmd_exec(["mega-ls", "-l", self.temp_path])
        if ret != 0 or not stdout:
            raise Exception("Mega Metadata Failed")

        lines = [line for line in stdout.strip().split("\n") if line.strip()]
        if not lines:
            raise Exception("Mega Import: No items found")

        for line in lines:
            match = re_search(
                r"\s(\d+|-)\s+\S+\s+\d{2}:\d{2}:\d{2}\s+(.*)$", line
            )
            if match:
                size_str = match.group(1)
                self.name = match.group(2).strip()
                self.size = int(size_str) if size_str.isdigit() else 0
                break

        if not self.name:
            s_stdout, _, _ = await cmd_exec(["mega-ls", self.temp_path])
            if s_stdout:
                self.name = s_stdout.strip().split("\n")[0].strip()

        if not self.name:
            self.name = self.listener.name or f"MEGA_Download_{self.gid}"

        self.listener.name = self.name
        self.listener.size = self.size

        return f"{self.temp_path}/{self.name}"

    async def cleanup(self):
        if self._is_cleaned:
            return
        self._is_cleaned = True
        try:
            LOGGER.info(f"Cleaning up Mega Task: {self.name}")
            await cmd_exec(["mega-rm", "-r", "-f", self.temp_path])
            if self.gid in mega_tasks:
                del mega_tasks[self.gid]
        except Exception as e:
            LOGGER.error(f"Mega Cleanup Failed: {e}")

    def _install_megacmd(self):
        if shutil.which('mega-get'):
            return True
        LOGGER.info("MEGAcmd not found, installing on the fly...")
        script = '''
        . /etc/os-release
        ARCH=$(dpkg --print-architecture)
        if [ "$NAME" = "Ubuntu" ]; then
            OS_URL="xUbuntu_${VERSION_ID}"
        elif [ "$NAME" = "Debian GNU/Linux" ]; then
            OS_URL="Debian_${VERSION_ID}"
        else
            OS_URL="xUbuntu_22.04"
        fi
        SUDO=""
        if command -v sudo >/dev/null 2>&1; then
            SUDO="sudo"
        fi
        $SUDO apt-get update -y || true
        DEB_NAME=$(curl -s "https://mega.nz/linux/repo/${OS_URL}/${ARCH}/" | \
grep -oP 'megacmd_[^"]*\\.deb' | head -n 1)
        if [ -z "$DEB_NAME" ]; then
            echo "Failed to find megacmd package for ${OS_URL}/${ARCH}"
            exit 1
        fi
        wget -qO megacmd.deb \
"https://mega.nz/linux/repo/${OS_URL}/${ARCH}/${DEB_NAME}"
        $SUDO DEBIAN_FRONTEND=noninteractive apt-get install -y ./megacmd.deb || \
        ($SUDO DEBIAN_FRONTEND=noninteractive apt-get install -f -y && $SUDO DEBIAN_FRONTEND=noninteractive apt-get install -y ./megacmd.deb)
        rm -f megacmd.deb
        if ! command -v mega-get &> /dev/null; then
            echo "MEGAcmd is not installed properly."
            exit 1
        fi
        '''
        try:
            py_subprocess.run(
                ["bash", "-c", script],
                check=True,
                capture_output=True,
                text=True
            )
            return True
        except py_subprocess.CalledProcessError as e:
            LOGGER.error(f"Failed to install MEGAcmd: {e.stdout}\n{e.stderr}")
            return False
        except Exception as e:
            LOGGER.error(f"Failed to install MEGAcmd: {e}")
            return False

    async def download(self, path):
        try:
            if not self._install_megacmd():
                return False
            await self.login()
            await self.create_temp_path()
            await self.import_link()
            target_node = await self.get_metadata_and_target()
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

            command = ["mega-get", target_node, path]

            self.process = await create_subprocess_exec(
                *command,
                stdout=asynciosubprocess.PIPE,
                stderr=asynciosubprocess.STDOUT,
            )

            while True:
                if getattr(self.listener, 'is_cancelled', False):
                    break

                try:
                    line_bytes = await wait_for(
                        self.process.stdout.readuntil(b"\r"), timeout=5
                    )
                    line = line_bytes.decode().strip()
                    if not line:
                        if self.process.returncode is not None:
                            break
                        continue
                    self._parse_progress(line)
                except TimeoutError:
                    await self.update_daemon_status()
                    if self.process.returncode is not None:
                        break
                    continue
                except Exception:
                    break

                if self.process.returncode is not None:
                    break

            await self.process.wait()

            if self.process.returncode == 0:
                await self.cleanup()
                await self.listener.onDownloadComplete()
                return True
            else:
                if getattr(self.listener, 'is_cancelled', False):
                    return True
                if self.process.returncode != -9:
                    err_msg = f"MegaCMD exited with {self.process.returncode}"
                    await self.listener.onDownloadError(err_msg)
                return True
        except Exception as e:
            if getattr(self.listener, 'is_cancelled', False):
                return True
            LOGGER.error(f"Mega Download Logic Error: {e}")
            await self.listener.onDownloadError(str(e))
            return True
        finally:
            await self.cleanup()

    def _parse_progress(self, line):
        muls = {"K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4, "B": 1}
        match = re_search(r"\(([\d\.]+)/([\d\.]+)\s([KMGT]?B)", line)
        if match:
            dl_val = float(match.group(1))
            unit_char = (match.group(3))[0].upper()
            mult = muls.get(unit_char, 1)
            self.mega_status._downloaded_bytes = int(dl_val * mult)

            if not self.listener.size or self.listener.size == 0:
                total_val = float(match.group(2))
                self.mega_status._size = int(total_val * mult)
                self.listener.size = self.mega_status._size

            cur_time = time()
            if cur_time - self._last_time >= 2:
                self.mega_status._speed = int(
                    (self.mega_status._downloaded_bytes - self._val_last)
                    / (cur_time - self._last_time)
                )
                self._last_time = cur_time
                self._val_last = self.mega_status._downloaded_bytes

    async def update_daemon_status(self):
        try:
            cmd = ["mega-transfers", "--col-separator=|"]
            stdout, _, _ = await cmd_exec(cmd)
            for line in stdout.splitlines():
                if self.gid in line:
                    parts = line.split("|")
                    if len(parts) > 1:
                        self.mega_tags.add(parts[1].strip())
                        if len(parts) > 4:
                            status = parts[5].strip().capitalize()
                            dl = MirrorStatus.STATUS_DOWNLOADING
                            if self.mega_status._status != dl:
                                self.mega_status._status = status
        except Exception:
            pass

    async def cancel_task(self):
        LOGGER.info(f"Cancelling {self.mega_status._status}: {self.name}")
        self.listener.is_cancelled = True

        await self.update_daemon_status()

        for tag in self.mega_tags:
            try:
                LOGGER.info(f"Cancelling Transfer Tag: {tag}")
                await cmd_exec(["mega-transfers", "-c", tag])
            except Exception as e:
                err = f"Mega Transfer Cancel Failed for {tag}: {e}"
                LOGGER.error(err)

        try:
            stdout, _, _ = await cmd_exec(["mega-transfers"])
            for line in stdout.splitlines():
                if self.gid in line:
                    parts = line.split()
                    if len(parts) > 1:
                        tag = parts[1]
                        if tag not in self.mega_tags:
                            LOGGER.info(f"Cancelling Straggler Tag: {tag}")
                            await cmd_exec(["mega-transfers", "-c", tag])
                        await cmd_exec(["mega-transfers", "-c", tag])
        except Exception as e:
            LOGGER.error(f"Mega Final Cancel Check Failed: {e}")

        if self.process is not None:
            with suppress(Exception):
                self.process.kill()

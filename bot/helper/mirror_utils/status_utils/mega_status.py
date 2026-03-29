from bot.helper.ext_utils.bot_utils import MirrorStatus
from bot.helper.ext_utils.status_utils import (
    get_readable_file_size,
    get_readable_time,
)


class MegaDownloadStatus:
    def __init__(self, listener, obj, gid, status):
        self.listener = listener
        self._obj = obj
        self._gid = gid
        self._status = status
        self.message = listener.message
        self._size = 0
        self._downloaded_bytes = 0
        self._speed = 0

    def gid(self):
        return self._gid

    def progress(self):
        try:
            return f"{round((self._downloaded_bytes / self._size) * 100, 2)}%"
        except:
            return "0.0%"

    def speed(self):
        return f"{get_readable_file_size(self._speed)}/s"

    def name(self):
        return self._obj.name or self.listener.name or "Mega Download"

    def size(self):
        return get_readable_file_size(self._size)

    def eta(self):
        try:
            seconds = (self._size - self._downloaded_bytes) / self._speed
            return get_readable_time(seconds)
        except:
            return "-"

    def status(self):
        return self._status

    def processed_bytes(self):
        return get_readable_file_size(self._downloaded_bytes)

    def download(self):
        return self._obj

    async def cancel_download(self):
        self.listener.is_cancelled = True
        await self._obj.cancel_task()
        await self.listener.onDownloadError("Download Cancelled by User!")

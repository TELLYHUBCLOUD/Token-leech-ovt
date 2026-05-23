import asyncio
import time
from bot import LOGGER, task_dict, task_dict_lock, bot_loop, config_dict
from bot.helper.ext_utils.status_utils import MirrorStatus
from bot.helper.telegram_helper.message_utils import sendMessage

class TaskWatchdog:
    def __init__(self):
        self.is_running = False
        self.task_cache = {}

    async def start(self):
        if self.is_running:
            return
        self.is_running = True
        bot_loop.create_task(self._watchdog_loop())

    async def _watchdog_loop(self):
        while self.is_running:
            await asyncio.sleep(300) # Check every 5 minutes
            try:
                stuck_timeout = int(config_dict.get('STUCK_TASK_TIMEOUT', 900))
                queue_timeout = int(config_dict.get('QUEUE_TASK_TIMEOUT', 1800))

                tasks_to_cancel = []
                async with task_dict_lock:
                    for mid, task in list(task_dict.items()):
                        gid = task.gid()
                        status = task.status()

                        if status in [MirrorStatus.STATUS_QUEUEDL, MirrorStatus.STATUS_QUEUEUP, MirrorStatus.STATUS_WAIT]:
                            if gid not in self.task_cache:
                                self.task_cache[gid] = {'added_time': time.time(), 'status': status}
                            else:
                                elapsed = time.time() - self.task_cache[gid]['added_time']
                                if elapsed > queue_timeout:
                                    tasks_to_cancel.append((task, "waiting in queue"))
                                    del self.task_cache[gid]
                                    continue
                        else:
                            if status in [MirrorStatus.STATUS_DOWNLOADING, MirrorStatus.STATUS_UPLOADING]:
                                current_progress = task.processed_bytes()
                                if gid not in self.task_cache:
                                    self.task_cache[gid] = {'last_progress': current_progress, 'last_time': time.time(), 'status': status}
                                else:
                                    if self.task_cache[gid]['status'] != status:
                                        self.task_cache[gid] = {'last_progress': current_progress, 'last_time': time.time(), 'status': status}
                                    elif self.task_cache[gid]['last_progress'] == current_progress:
                                        elapsed = time.time() - self.task_cache[gid]['last_time']
                                        if elapsed > stuck_timeout:
                                            tasks_to_cancel.append((task, "inactivity/zero progress"))
                                            del self.task_cache[gid]
                                            continue
                                    else:
                                        self.task_cache[gid]['last_progress'] = current_progress
                                        self.task_cache[gid]['last_time'] = time.time()

                for task, reason in tasks_to_cancel:
                    LOGGER.warning(f"Task {task.name()} auto-removed due to {reason}.")
                    await self._cancel_and_notify(task, reason)

            except Exception as e:
                LOGGER.error(f"Watchdog Error: {e}")

    async def _cancel_and_notify(self, task, reason):
        try:
            message = getattr(task.listener, 'message', None)
            if message:
                await sendMessage(f"⚠️ Your task <code>{task.name()}</code> was automatically removed due to {reason}.", message)

            if hasattr(task, 'cancel_task'):
                await task.cancel_task()
            elif hasattr(task.listener, 'onDownloadError'):
                await task.listener.onDownloadError(f"Cancelled by Watchdog: {reason}")
            elif hasattr(task.listener, 'onUploadError'):
                await task.listener.onUploadError(f"Cancelled by Watchdog: {reason}")

            import os, shutil
            try:
                temp_path = getattr(task.listener, 'dir', None)
                if not temp_path and hasattr(task, 'temp_path'):
                    temp_path = getattr(task, 'temp_path', None)
                if temp_path and os.path.exists(temp_path):
                    shutil.rmtree(temp_path, ignore_errors=True)
            except:
                pass
        except Exception as e:
            LOGGER.error(f"Watchdog Cancel Error: {e}")

watchdog = TaskWatchdog()

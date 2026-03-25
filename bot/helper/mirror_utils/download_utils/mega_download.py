from bot.helper.listeners.mega_listener import MegaAppListener


async def add_mega_download(listener, path):
    mega_listener = MegaAppListener(listener)
    success = await mega_listener.download(path)
    if success is False:
        from bot import LOGGER
        from bot.helper.mirror_utils.download_utils.jd_download import add_jd_download

        LOGGER.info("Falling back to JDownloader for MEGA link...")
        listener.isJd = True
        try:
            await add_jd_download(listener, path)
        except Exception as e:
            LOGGER.error(f"Fallback JDownloader failed: {e}")

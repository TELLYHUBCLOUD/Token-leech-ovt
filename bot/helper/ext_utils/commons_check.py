from asyncio import gather
from pyrogram.errors import UserDeactivated
from pyrogram.types import Message
from time import time
from uuid import uuid4

from bot import bot_loop, bot_name, task_dict, task_dict_lock, config_dict, user_data
from bot.helper.ext_utils.bot_utils import get_user_task, is_premium_user, update_user_ldata, sync_to_async, UserDaily
from bot.helper.ext_utils.shortenurl import short_url
from bot.helper.ext_utils.status_utils import get_readable_time
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.telegram_helper.button_build import ButtonMaker
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.message_utils import sendingMessage


class UseCheck:
    def __init__(self, message: Message, is_leech: bool=False):
        self._message = message
        self._is_leech = is_leech
        self._uid = message.from_user.id
        self._user_dict: dict = user_data.get(self._uid, {})
        self.isPremi = is_premium_user(self._uid, getattr(message.chat, 'id', None))
        bot_loop.create_task(self._check_limit())

    async def run(self, limit=False, forpremi=False, daily=False, ml_chek=False, session=False, send_pm=False):
        msgs = []
        buttons = ButtonMaker()

        if msg := await self._force_sub(buttons):
            msgs.append(msg)
        if msg := await self._force_username():
            msgs.append(msg)
        if limit and (msg := await self._task_limiter()):
            msgs.append(msg)
        if forpremi and (msg := self._check_premium()):
            msgs.append(msg)
        if daily and (msg := await self._daily_limit()):
            msgs.append(msg)
        if ml_chek and (msg := self._check_ml()):
            msgs.append(msg)
        if session and (msg := await self._check_session(buttons)):
            msgs.append(msg)
        if send_pm and self._user_dict.get('enable_pm') and self._message.chat.type.name in ['SUPERGROUP', 'CHANNEL'] and (msg := await self._send_pm(buttons)):
            msgs.append(msg)

        if msgs:
            return await sendingMessage(f'Hey there {self._message.from_user.mention}...\n\n' + '\n'.join(msgs), self._message, config_dict['IMAGE_COMMONS_CHECK'], buttons.build_menu(2))

    async def _send_pm(self, buttons):
        try:
            user = await self._message._client.get_users(self._uid)
            if user.status.name == 'LONG_AGO':
                raise UserDeactivated('User is inactive!')
        except:
            buttons.button_link('Start PM', f'http://t.me/{bot_name}')
            return '⁍ I have no access to Private Message, '

    async def _force_username(self):
        if config_dict['FUSERNAME']:
            uname = self._message.from_user.username
            if not uname:
                return '⁍ Set username: Go to <b>Settings</b> -> <b>My Account</b> -> <b>Username</b>.'
            if self._user_dict.get('user_name', '') != uname:
                await update_user_ldata(self._uid, 'user_name', self._message.from_user.username)

    def _check_ml(self):
        if mode := str(config_dict['DISABLE_MIRROR_LEECH']):
            if mode == 'mirror' and not self._is_leech:
                return '⁍ Mirror mode has been disabled!'
            if mode == 'leech' and self._is_leech:
                return '⁍ Leech mode has been disabled!'


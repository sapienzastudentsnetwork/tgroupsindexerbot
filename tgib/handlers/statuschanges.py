# Copyright (C) 2022-2023, Matteo Collica (Matypist)
#
# This file is part of the "Telegram Groups Indexer Bot" (TGroupsIndexerBot)
# project, the original source of which is the following GitHub repository:
# <https://github.com/sapienzastudentsnetwork/tgroupsindexerbot>.
#
# TGroupsIndexerBot is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# TGroupsIndexerBot is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with TGroupsIndexerBot. If not, see <http://www.gnu.org/licenses/>.

from telegram import Update, ChatMember, Chat
from telegram.ext import ContextTypes

from tgib.data.database import ChatTable
from tgib.logs import Logger


class StatusChanges:
    @classmethod
    async def migrate_handler(cls, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        message = update.message

        if message.migrate_to_chat_id is not None:
            old_chat_id = message.chat_id
            new_chat_id = message.migrate_to_chat_id

            Logger.log("info", "StatusChanges.migrate_handler",
                       f"The group having chat_id = '{old_chat_id}'"
                       f" migrated to a supergroup with chat_id = '{new_chat_id}'")

            ChatTable.migrate_chat_id(old_chat_id, new_chat_id)

    @classmethod
    async def my_chat_member_handler(cls, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        chat = update.effective_chat

        bot = context.bot

        chat_member_update = update.my_chat_member

        status_change = chat_member_update.difference().get("status")

        old_is_member, new_is_member = chat_member_update.difference().get("is_member", (None, None))

        if status_change is None:
            return None

        old_status, new_status = status_change

        was_member = old_status in [ChatMember.MEMBER, ChatMember.ADMINISTRATOR, ChatMember.OWNER] \
                     or (old_status == ChatMember.RESTRICTED and old_is_member is True)

        is_member = new_status in [ChatMember.MEMBER, ChatMember.ADMINISTRATOR, ChatMember.OWNER] \
                    or (new_status == ChatMember.RESTRICTED and new_is_member is True)

        chat_type = chat.type

        if chat_type in [Chat.GROUP, Chat.SUPERGROUP]:
            chat_id = chat.id

            if not was_member and is_member:
                Logger.log("info", "StatusChanges.my_chat_member_handler",
                           f"The bot was added to the group with chat_id = '{chat_id}'")

                await ChatTable.fetch_chat(bot, chat_id)

            elif old_status in (ChatMember.RESTRICTED, ChatMember.MEMBER) and new_status == ChatMember.ADMINISTRATOR:
                Logger.log("info", "StatusChanges.my_chat_member_handler",
                           f"The bot was made administrator in the group with chat_id = '{chat_id}'")

                await ChatTable.fetch_chat(bot, chat_id)

            elif was_member and not is_member:
                Logger.log("info", "StatusChanges.my_chat_member_handler",
                           f"The bot was kicked from the group with chat_id = '{chat_id}'")

                ChatTable.remove_chat(chat_id)

            elif old_status == ChatMember.ADMINISTRATOR and new_status in (ChatMember.RESTRICTED, ChatMember.MEMBER):
                Logger.log("info", "StatusChanges.my_chat_member_handler",
                           f"The bot was removed administrator from the group with chat_id = '{chat_id}'")

                ChatTable.set_missing_permissions(chat_id)

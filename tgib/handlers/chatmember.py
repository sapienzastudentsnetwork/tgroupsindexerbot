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


class MemberStatusUpdates:
    @classmethod
    async def member_status_updates_handler(cls, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
                Logger.log("info", "MemberStatusUpdates.member_status_updates_handler",
                           "Il bot è stato aggiunto nel gruppo con chat_id = " + str(chat_id))

                await ChatTable.fetch_chat(bot, chat_id)

            elif old_status in (ChatMember.RESTRICTED, ChatMember.MEMBER) and new_status == ChatMember.ADMINISTRATOR:
                Logger.log("info", "MemberStatusUpdates.member_status_updates_handler",
                           "Il bot è stato reso amministratore nel gruppo con chat_id = " + str(chat_id))

                await ChatTable.fetch_chat(bot, chat_id)

            elif was_member and not is_member:
                Logger.log("info", "MemberStatusUpdates.member_status_updates_handler",
                           "Il bot è stato rimosso dal gruppo con chat_id = " + str(chat_id))

                await ChatTable.remove_chat(chat_id)

            elif old_status == ChatMember.ADMINISTRATOR and new_status in (ChatMember.RESTRICTED, ChatMember.MEMBER):
                Logger.log("info", "MemberStatusUpdates.member_status_updates_handler",
                           "Il bot è stato tolto amministratore dal gruppo con chat_id = " + str(chat_id))

                await ChatTable.set_missing_permissions(chat_id)

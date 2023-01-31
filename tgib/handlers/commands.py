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

from telegram import Update
from telegram.ext import ContextTypes

from tgib.data.database import SessionTable, DirectoryTable
from tgib.handlers.queries import Queries
from tgib.i18n.locales import Locale
from tgib.ui.menus import Menus


class Commands:
    @classmethod
    async def commands_handler(cls, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        bot           = context.bot
        chat_id       = update.effective_chat.id
        query_message = update.message

        if query_message.chat.type == "private":
            command = query_message.text.split()[0][1:]

            if Queries.user_can_perform_action(chat_id, "/" + command):
                locale = Locale(update.effective_user.language_code)

                text, reply_markup = "", None

                if command == "start":
                    text, reply_markup = Menus.get_main_menu(locale)

                elif command == "groups":
                    text, reply_markup = Queries.explore_category(locale, DirectoryTable.CATEGORIES_ROOT_DIR_ID)

                if text or reply_markup:
                    reply_markup = Queries.encode_queries(reply_markup)

                    new_message = await bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)

                    try:
                        await bot.delete_message(chat_id=chat_id, message_id=query_message.message_id)
                    except:
                        pass

                    old_latest_menu_message_id = SessionTable.get_active_session_menu_message_id(chat_id)

                    if old_latest_menu_message_id != -1:
                        try:
                            await bot.delete_message(chat_id=chat_id, message_id=old_latest_menu_message_id)
                        except:
                            pass

                        SessionTable.update_session(chat_id, new_message.message_id)
                    else:
                        SessionTable.add_session(chat_id, new_message.message_id)

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

import telegram.error
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from tgib.data.database import SessionTable, DirectoryTable, AccountTable
from tgib.global_vars import GlobalVariables
from tgib.handlers.queries import Queries
from tgib.i18n.locales import Locale
from tgib.ui.menus import Menus


class Commands:
    @classmethod
    async def commands_handler(cls, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        bot           = context.bot
        chat_id       = update.effective_chat.id
        user_id       = update.effective_user.id
        query_message = update.message

        if query_message.chat.type != "channel":
            command = query_message.text.split()[0][1:]

            locale = Locale(update.effective_user.language_code)

            text, reply_markup = "", None

            user_data, is_user_data = AccountTable.get_account_record(user_id, create_if_not_existing=(query_message.chat.type == "private"))

            if not is_user_data and query_message.chat.type == "private":
                text, reply_markup = Menus.get_database_error_menu(locale)
            else:
                if (is_user_data and Queries.user_can_perform_action(user_id, user_data, "/" + command)) or (not is_user_data):
                    if (command == "start" and query_message.chat.type == "private") or (command == "start@" + bot.username):
                        text, reply_markup = Menus.get_main_menu(locale)

                    elif command in ("groups", "groups@" + bot.username):
                        text, reply_markup = Queries.explore_category(locale, DirectoryTable.CATEGORIES_ROOT_DIR_ID, user_data["is_admin"])

            if text or reply_markup:
                reply_markup = Queries.encode_queries(reply_markup)

                new_message = None

                error_message = None

                try:
                    new_message = await bot.send_message(chat_id=user_id, text=text, reply_markup=reply_markup)

                    if not is_user_data and query_message.chat.type != "private":
                        user_data, is_user_data = AccountTable.get_account_record(user_id, create_if_not_existing=True)
                except telegram.error.Forbidden as ex:
                    if "bot was blocked by the user" in ex.message:
                        error_message = locale.get_string("commands.groups.errors.forbidden.blocked_by_user")
                except telegram.error.BadRequest as ex:
                    if "Chat not found" in ex.message:
                        error_message = locale.get_string("commands.groups.errors.badrequest.chat_not_found")
                except:
                    pass

                if query_message.chat.type != "private" and not new_message:
                    if not error_message:
                        error_message = locale.get_string("commands.groups.error")

                    text = error_message\
                        .replace("[user]", f'<a href="tg://user?id={user_id}">' + update.effective_user.first_name + '</a>')\
                        .replace("[command]", f'/<a href="/{command}">' + command.replace("@" + bot.username, "") + "</a>")

                    reply_markup = InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton(
                                text=locale.get_string("commands.groups.goto_bot_btn"),
                                url=f'tg://resolve?domain=' + bot.username
                            )
                        ]
                    ])

                    try:
                        new_message = await bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)

                        job_queue = GlobalVariables.job_queue
                        job_queue: telegram.ext.Application.job_queue

                        async def delete_message(context: ContextTypes.DEFAULT_TYPE) -> None:
                            await bot.delete_message(chat_id=chat_id, message_id=new_message.message_id)

                        job_queue.run_once(callback=delete_message, when=10)
                    except:
                        pass

                try:
                    await bot.delete_message(chat_id=chat_id, message_id=query_message.message_id)
                except:
                    pass

                if is_user_data and not error_message and new_message:
                    old_latest_menu_message_id = SessionTable.get_active_session_menu_message_id(user_id)

                    if old_latest_menu_message_id != -1:
                        try:
                            await bot.delete_message(chat_id=user_id, message_id=old_latest_menu_message_id)
                        except:
                            pass

                        SessionTable.update_session(user_id, new_message.message_id)
                    else:
                        SessionTable.add_session(user_id, new_message.message_id)

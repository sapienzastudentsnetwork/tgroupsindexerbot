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

import time

import telegram.error
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from tgib.data.database import SessionTable, DirectoryTable, AccountTable
from tgib.global_vars import GlobalVariables
from tgib.handlers.queries import Queries
from tgib.i18n.locales import Locale
from tgib.ui.menus import Menus


class Commands:
    command_cooldowns = {"dont": 15, "reload": 30, "netstatus": 60}
    user_last_command_use_dates = {"dont": {}, "reload": {}, "netstatus": {}}
    registered_commands = ["start", "groups", "dont"]

    @classmethod
    async def commands_handler(cls, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        bot           = context.bot
        chat_id       = update.effective_chat.id
        user_id       = update.effective_user.id
        query_message = update.message

        if query_message.chat.type != "channel":
            command = query_message.text.split()[0][1:].lower()

            bot_username_lower = bot.username.lower()

            locale = Locale(update.effective_user.language_code)

            is_a_registered_command = False

            for registered_command in cls.registered_commands:
                if command == registered_command or command == f"{registered_command}@{bot_username_lower}":
                    is_a_registered_command = True

                    break

            if not is_a_registered_command:
                if command.endswith(bot_username_lower):
                    text = locale.get_string("commands.command_not_found.text") \
                        .replace("[user]",
                                 f'<a href="tg://user?id={user_id}">' + update.effective_user.first_name + '</a>') \
                        .replace("[command]",
                                 f'<code>/' + command.replace("@" + bot_username_lower, "") + "</code>")

                    keyboard = [
                        [InlineKeyboardButton(text=locale.get_string("commands.command_not_found.contact_us_btn"),
                                              url="tg://resolve?domain=sapienzastudentsnetworkbot")],
                    ]

                    reply_markup = InlineKeyboardMarkup(keyboard)

                    try:
                        new_message = await bot.send_message(chat_id=user_id, text=text, reply_markup=reply_markup)
                    except:
                        new_message = await bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)

                        async def delete_message(context: ContextTypes.DEFAULT_TYPE) -> None:
                            try:
                                await bot.delete_message(chat_id=chat_id, message_id=new_message.message_id)
                            except:
                                pass

                        GlobalVariables.job_queue.run_once(callback=delete_message, when=10)

                    try:
                        await bot.delete_message(chat_id=chat_id, message_id=query_message.message_id)
                    except:
                        pass

                return

            text, reply_markup, reply_to_message = None, None, None

            user_data, is_user_data = AccountTable.get_account_record(
                user_id,
                create_if_not_existing=(query_message.chat.type == "private")
            )

            cooldown = False

            if not is_user_data and query_message.chat.type == "private":
                text, reply_markup = Menus.get_database_error_menu(locale)
            else:
                if (is_user_data and Queries.user_can_perform_action(user_id, user_data, "/" + command)) or (not is_user_data):
                    if command == "start" and query_message.chat.type != "private":
                        return

                    invalid_request = False

                    if command == "start" or command == "start@" + bot_username_lower:
                        text, reply_markup = Menus.get_main_menu(locale)

                    elif command in ("groups", "groups@" + bot_username_lower):
                        text, reply_markup = Queries.explore_category(
                            locale,
                            DirectoryTable.CATEGORIES_ROOT_DIR_ID,
                            user_data["can_add_groups"], user_data["is_admin"]
                        )

                    else:
                        if command in ("reload",) and query_message.chat.type == "private":
                            text = locale.get_string("commands.groups.group_specific_command") \
                                .replace("[command]",
                                         f'/<a href="/{command}">' + command.replace("@" + bot_username_lower, "") + "</a>")

                            invalid_request = True

                        elif command in ("reload",) and not ((user_data and user_data["is_admin"]) or await Queries.is_admin(bot, chat_id, user_id)):
                            text = locale.get_string("commands.groups.admin_specific_command") \
                                .replace("[user]",
                                         f'<a href="tg://user?id={user_id}">' + update.effective_user.first_name + '</a>') \
                                .replace("[command]",
                                         f'/<a href="/{command}">' + command.replace("@" + bot_username_lower, "") + "</a>")

                            invalid_request = True

                        if not invalid_request:
                            if command == "dont":
                                text = ""

                                for lang_code in Locale.lang_codes:
                                    text += "\n\n" + Locale(lang_code).get_string("commands.dont")

                                if query_message.reply_to_message:
                                    reply_to_message = query_message.reply_to_message

                    if query_message.chat.type != "private" and not invalid_request and command in cls.command_cooldowns:
                        current_epoch = int(time.time())

                        if user_id in cls.user_last_command_use_dates[command]:
                            time_difference = current_epoch - cls.user_last_command_use_dates[command][user_id]

                            minimum_time_difference_required = cls.command_cooldowns[command]

                            if time_difference >= minimum_time_difference_required:
                                cls.user_last_command_use_dates[command][user_id] = current_epoch
                            else:
                                text = locale.get_string("commands.groups.cooldown") \
                                    .replace("[user]",
                                             f'<a href="tg://user?id={user_id}">' + update.effective_user.first_name + '</a>') \
                                    .replace("[command]",
                                             f'/<a href="/{command}">' + command.replace("@" + bot_username_lower,
                                                                                         "") + "</a>") \
                                    .replace("[remaining_time]",
                                             str(minimum_time_difference_required - time_difference))

                                cooldown = True

                        else:
                            cls.user_last_command_use_dates[command][user_id] = current_epoch

            if reply_markup:
                reply_markup = Queries.encode_queries(reply_markup)

            if command.startswith("start") or command.startswith("groups"):
                new_message, error_message = None, None

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

                    text = error_message \
                        .replace("[user]",
                                 f'<a href="tg://user?id={user_id}">' + update.effective_user.first_name + '</a>') \
                        .replace("[command]",
                                 f'/<a href="/{command}">' + command.replace("@" + bot_username_lower, "") + "</a>")

                    reply_markup = InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton(
                                text=locale.get_string("commands.groups.goto_bot_btn"),
                                url=f'tg://resolve?domain=' + bot_username_lower
                            )
                        ]
                    ])

                    try:
                        new_message = await bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)

                        job_queue = GlobalVariables.job_queue
                        job_queue: telegram.ext.Application.job_queue

                        async def delete_message(context: ContextTypes.DEFAULT_TYPE) -> None:
                            try:
                                await bot.delete_message(chat_id=chat_id, message_id=new_message.message_id)
                            except:
                                pass

                        job_queue.run_once(callback=delete_message, when=10)
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

            else:
                message_chat_id = chat_id

                if cooldown or not reply_to_message:
                    if cooldown:
                        try:
                            new_message = await bot.send_message(chat_id=user_id, text=text)

                            message_chat_id = user_id
                        except:
                            new_message = await bot.send_message(chat_id=chat_id, text=text)
                    else:
                        new_message = await bot.send_message(chat_id=chat_id, text=text)
                else:
                    reply_to_message: telegram.Message

                    new_message = await reply_to_message.reply_text(text=text)

                if cooldown or command not in ("dont",):
                    async def delete_message(context: ContextTypes.DEFAULT_TYPE) -> None:
                        try:
                            await bot.delete_message(chat_id=message_chat_id, message_id=new_message.message_id)
                        except:
                            pass

                    GlobalVariables.job_queue.run_once(callback=delete_message, when=10)

            try:
                await bot.delete_message(chat_id=chat_id, message_id=query_message.message_id)
            except:
                pass

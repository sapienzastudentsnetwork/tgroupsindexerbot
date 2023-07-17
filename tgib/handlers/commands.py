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
import os
import time

import telegram.error
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatMemberAdministrator
from telegram.ext import ContextTypes

from tgib.data.database import SessionTable, DirectoryTable, AccountTable, ChatTable
from tgib.global_vars import GlobalVariables
from tgib.handlers.queries import Queries
from tgib.i18n.locales import Locale
from tgib.ui.menus import Menus


class Commands:
    command_cooldowns = {"dont": 15, "reload": 15, "netstatus": 60}
    user_last_command_use_dates = {"dont": {}, "reload": {}, "netstatus": {}}
    registered_commands = ["start", "groups", "dont", "reload", "id",
                           "hide", "unhide", "move", "unindex",
                           "addadmin", "rmadmin", "listadmins"]
    private_specific_commands = ("addadmin", "rmadmin")
    group_specific_commands = ("reload",)
    group_admin_commands = ("reload",)
    bot_admin_commands = ("hide", "unhide", "move", "unindex")
    bot_owner_commands = ("addadmin", "rmadmin", "listadmins")
    alias_commands = {"removeadmin": "rmadmin", "bangroup": "hide", "unbangroup": "unhide", "deindex": "unindex"}

    @classmethod
    async def commands_handler(cls, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        bot           = context.bot
        chat_id       = update.effective_chat.id
        user_id       = update.effective_user.id
        query_message = update.message

        if query_message.chat.type != "channel":
            bot_username_lower = bot.username.lower()

            command = query_message.text.split()[0][1:].lower()

            command_name = command.replace("@" + bot_username_lower, "")

            if command_name in cls.alias_commands:
                command_name = cls.alias_commands[command_name]

            command_args = query_message.text.split(" ")[1:]

            locale = Locale(update.effective_user.language_code)

            is_a_registered_command = (command_name in cls.registered_commands)

            if not is_a_registered_command:
                if command.endswith(bot_username_lower) or update.effective_chat.type == "private":
                    text = locale.get_string("commands.command_not_found.text") \
                        .replace("[user]",
                                 f'<a href="tg://user?id={user_id}">' + update.effective_user.first_name + '</a>') \
                        .replace("[command]", f'<code>/' + command_name + "</code>")

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

            user_is_bot_admin = (is_user_data and user_data and user_data["is_admin"])

            auto_delete_delay = 10

            cooldown = False

            delete_query_message = True

            invalid_request = False

            bot_owner_chat_id = GlobalVariables.bot_owner

            if not is_user_data and query_message.chat.type == "private":
                text, reply_markup = Menus.get_error_menu(locale, source="database")
            else:
                if (is_user_data and Queries.user_can_perform_action(user_id, user_data, "/" + command_name)) or (not is_user_data):
                    if command_name == "start":
                        text, reply_markup = Menus.get_main_menu(locale)

                    elif command_name == "groups":
                        text, reply_markup = Queries.explore_category(
                            locale,
                            DirectoryTable.CATEGORIES_ROOT_DIR_ID,
                            user_data["can_add_groups"], user_data["is_admin"]
                        )

                    else:
                        if command_name in cls.group_specific_commands and query_message.chat.type == "private":
                            text = locale.get_string("commands.groups.group_specific_command") \
                                .replace("[command]",
                                         f'/<a href="/{command}">' + command_name + "</a>")

                            invalid_request = True

                        elif command_name in cls.private_specific_commands and query_message.chat.type != "private":
                            delete_query_message = False

                            invalid_request = True

                        elif command_name in cls.group_admin_commands and not user_is_bot_admin and not Queries.is_admin(bot, chat_id, user_id):
                            text = locale.get_string("commands.groups.admin_specific_command") \
                                .replace("[user]",
                                         f'<a href="tg://user?id={user_id}">' + update.effective_user.first_name + '</a>') \
                                .replace("[command]", f'/<a href="/{command}">' + command_name + "</a>")

                            invalid_request = True

                        elif command_name in cls.bot_admin_commands and not user_is_bot_admin:
                            text = locale.get_string("commands.bot_admin_specific_command") \
                                .replace("[user]",
                                         f'<a href="tg://user?id={user_id}">' + update.effective_user.first_name + '</a>') \
                                .replace("[command]", f'/<a href="/{command}">' + command_name + "</a>")

                            invalid_request = True

                        elif command_name in cls.bot_owner_commands and (bot_owner_chat_id is None or bot_owner_chat_id != str(user_id)):
                            text = locale.get_string("commands.bot_owner_specific_command") \
                                .replace("[user]",
                                         f'<a href="tg://user?id={user_id}">' + update.effective_user.first_name + '</a>') \
                                .replace("[command]", f'/<a href="/{command}">' + command_name + "</a>")

                            invalid_request = True

                        if not invalid_request:
                            if command_name == "dont":
                                text = ""

                                for lang_code in Locale.lang_codes:
                                    text += "\n\n" + Locale(lang_code).get_string("commands.dont")

                                if query_message.reply_to_message:
                                    reply_to_message = query_message.reply_to_message

                            elif command_name == "reload":
                                old_chat_data, new_chat_data, is_new_chat_data = await ChatTable.fetch_chat(bot, chat_id)

                                if is_new_chat_data:
                                    bot_member = await bot.get_chat_member(chat_id, bot.id)

                                    text = locale.get_string("commands.reload.successful")

                                    if not isinstance(bot_member, ChatMemberAdministrator):
                                        text += "\n\n" + locale.get_string("commands.reload.is_not_admin")

                                        auto_delete_delay = 15

                                    elif isinstance(bot_member, ChatMemberAdministrator):
                                        bot_member: ChatMemberAdministrator

                                        if not bot_member.can_invite_users:
                                            try:
                                                chat = await bot.get_chat(chat_id)

                                                chat_permissions = chat.permissions

                                                text += "\n\n"

                                                if chat_permissions.can_invite_users:
                                                    text += locale.get_string("commands.reload.cant_invite_users_via_link")
                                                else:
                                                    text += locale.get_string("commands.reload.cant_add_members")

                                                auto_delete_delay = 15
                                            except:
                                                text = locale.get_string("commands.reload.unsuccessful")

                                else:
                                    text = locale.get_string("commands.reload.unsuccessful")

                            elif command_name in ("hide", "unhide", "move", "unindex"):
                                target_chat_id = None

                                query_msg_text = query_message.text

                                if update.effective_chat.type in ("group", "supergroup"):
                                    target_chat_id = chat_id

                                else:
                                    if len(command_args) >= 1:
                                        try:
                                            target_chat_id = int(query_msg_text.split(" ")[1])

                                        except:
                                            text = locale.get_string("commands.wrong_chat_id_format")

                                            delete_query_message = False
                                    else:
                                        text = locale.get_string("commands.min_n_args")

                                        if command_name == "move":
                                            text = text.replace("[n]", "2")
                                        else:
                                            text = text.replace("[n]", "1")

                                        invalid_request = True

                                if invalid_request is False and target_chat_id is not None:
                                    target_chat_data, is_target_chat_data = ChatTable.get_chat_data(target_chat_id)

                                    if not is_target_chat_data:
                                        text = locale.get_string("commands.chat_database_error")

                                        delete_query_message = False

                                    else:
                                        chat_directory_id = None

                                        if target_chat_data["directory_id"] is not None:
                                            chat_directory_id = target_chat_data["directory_id"]

                                        if command_name == "hide":
                                            if target_chat_data["hidden_by"] is None:
                                                updated = ChatTable.update_chat_visibility(target_chat_id, hidden_by=user_id)

                                                if updated:
                                                    if chat_directory_id is not None:
                                                        DirectoryTable.increment_chats_count(chat_directory_id, -1)

                                                    text = locale.get_string("commands.visibility.hide.successful")

                                            else:
                                                text = locale.get_string("commands.visibility.already_hidden")

                                        elif command_name == "unhide":
                                            if target_chat_data["hidden_by"] is not None:
                                                updated = ChatTable.update_chat_visibility(target_chat_id, hidden_by=None)

                                                if updated:
                                                    if chat_directory_id is not None:
                                                        DirectoryTable.increment_chats_count(chat_directory_id, +1)

                                                    text = locale.get_string("commands.visibility.unhide.successful")

                                            else:
                                                text = locale.get_string("commands.visibility.already_not_hidden")

                                        elif command_name == "move":
                                            try:
                                                if update.effective_chat.type not in ("group", "supergroup"):
                                                    if len(command_args) == 2:
                                                        target_directory_id = int(query_msg_text.split(" ")[2])

                                                    else:
                                                        text = locale.get_string("commands.min_n_args").replace("[n]", "2")

                                                        invalid_request = True

                                                else:
                                                    target_directory_id = int(query_msg_text.split(" ")[1])

                                                if not invalid_request:
                                                    full_category_name = DirectoryTable.get_full_category_name(locale.lang_code, target_directory_id)

                                                    if full_category_name is not None:
                                                        if chat_directory_id is None or target_directory_id != chat_directory_id:
                                                            updated = ChatTable.update_chat_directory(target_chat_id, target_directory_id)

                                                            if updated:
                                                                DirectoryTable.increment_chats_count(target_directory_id, +1)

                                                                if chat_directory_id is not None:
                                                                    DirectoryTable.increment_chats_count(chat_directory_id, -1)

                                                                text = locale.get_string("commands.move.successful")

                                                            else:
                                                                text = locale.get_string("commands.directory_database_error")

                                                        else:
                                                            text = locale.get_string("commands.move.already_current_category")

                                                        text = text.replace("[category]", full_category_name)

                                                    else:
                                                        text = locale.get_string("commands.directory_database_error")

                                            except:
                                                text = locale.get_string("commands.wrong_directory_id_format")

                                                delete_query_message = False

                                        elif command_name == "unindex":
                                            if chat_directory_id is not None:
                                                updated = ChatTable.update_chat_directory(target_chat_id, None)

                                                if updated:
                                                    DirectoryTable.increment_chats_count(chat_directory_id, -1)

                                                    text = locale.get_string("commands.visibility.unindex.successful")

                                            else:
                                                text = locale.get_string("commands.visibility.already_not_indexed_at_all")

                                        if text:
                                            text = text.replace("[title]", target_chat_data["title"]).replace("[chat_id]", str(target_chat_id))
                                        else:
                                            text = locale.get_string("commands.database_error")

                                            delete_query_message = False

                            elif command_name in ("addadmin", "rmadmin"):
                                if len(command_args) >= 1:
                                    target_chat_id = None

                                    try:
                                        target_chat_id = int(command_args[0])

                                    except:
                                        text = locale.get_string("commands.wrong_chat_id_format")

                                        delete_query_message = False

                                    if target_chat_id is not None:
                                        target_chat_data, is_target_chat_data = AccountTable.get_account_record(target_chat_id, False)

                                        if is_target_chat_data:
                                            updated = False

                                            if command_name == "addadmin":
                                                if target_chat_data["is_admin"] is False:
                                                    updated = AccountTable.update_admin_status(target_chat_id, True)

                                                    if updated:
                                                        text = locale.get_string("commands.admins.set")

                                                else:
                                                    text = locale.get_string("commands.admins.already_admin")

                                            elif command_name == "rmadmin":
                                                if target_chat_data["is_admin"] is True:
                                                    updated = AccountTable.update_admin_status(target_chat_id, False)

                                                    if updated:
                                                        text = locale.get_string("commands.admins.unset")

                                                else:
                                                    text = locale.get_string("commands.admins.already_not_admin")

                                            if text:
                                                text = text.replace("[chat_id]", str(target_chat_id))

                                            if updated:
                                                delete_query_message = False

                                            elif not text:
                                                delete_query_message = False

                                                text = locale.get_string("commands.admins.database_error")


                                        else:
                                            text = locale.get_string("commands.chat_database_error")

                                            delete_query_message = False

                                else:
                                    text = locale.get_string("commands.min_n_args").replace("[n]", "1")

                                    invalid_request = True

                            elif command_name == "listadmins":
                                records_dict, is_records_dict = AccountTable.get_bot_admin_records()

                                if is_records_dict:
                                    if records_dict:
                                        date_str, time_str, offset_str = Queries.get_current_italian_datetime()

                                        text = locale.get_string("commands.admins.list.first_line")

                                        for bot_admin_chat_id, bot_admin_data in records_dict.items():
                                            bot_admin_name = bot_admin_chat_id

                                            chat = None

                                            try:
                                                chat = await bot.get_chat(bot_admin_chat_id)
                                                chat: telegram.Chat

                                                bot_admin_name = chat.full_name

                                            except Exception as ex:
                                                pass

                                            text += f'\n\n• <a href="tg://user?id={bot_admin_chat_id}">{bot_admin_name}</a>'

                                            if chat and chat.username is not None:
                                                text += f" (@{chat.username})"

                                            text += f" [<code>{bot_admin_chat_id}</code>]"

                                        text += "\n\n" + locale.get_string("commands.admins.list.generation_date_line") \
                                            .replace("[date]", date_str) \
                                            .replace("[time]", time_str) \
                                            .replace("[offset]", offset_str[1:3]) + "\n"
                                    else:
                                        text = locale.get_string("commands.admins.list.empty")

                                else:
                                    delete_query_message = False

                                    text = locale.get_string("commands.admins.database_error")

                            elif command_name == "id":
                                text = locale.get_string("commands.id").replace("[chat_id]", str(chat_id))

                    if query_message.chat.type != "private" and not invalid_request and not user_is_bot_admin and command_name in cls.command_cooldowns:
                        current_epoch = int(time.time())

                        if user_id in cls.user_last_command_use_dates[command_name]:
                            time_difference = current_epoch - cls.user_last_command_use_dates[command_name][user_id]

                            minimum_time_difference_required = cls.command_cooldowns[command_name]

                            if time_difference >= minimum_time_difference_required:
                                cls.user_last_command_use_dates[command_name][user_id] = current_epoch
                            else:
                                text = locale.get_string("commands.groups.cooldown") \
                                    .replace("[user]",
                                             f'<a href="tg://user?id={user_id}">' + update.effective_user.first_name + '</a>') \
                                    .replace("[command]", f'/<a href="/{command}">' + command_name + "</a>") \
                                    .replace("[remaining_time]", str(minimum_time_difference_required - time_difference))

                                cooldown = True

                        else:
                            cls.user_last_command_use_dates[command_name][user_id] = current_epoch

            if reply_markup:
                reply_markup = Queries.encode_queries(reply_markup)

            if command_name in ("start", "groups"):
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
                        .replace("[command]", f'/<a href="/{command}">' + command_name + "</a>")

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

                new_message = None

                if cooldown or not reply_to_message:
                    if cooldown:
                        try:
                            new_message = await bot.send_message(chat_id=user_id, text=text)

                            message_chat_id = user_id
                        except:
                            try:
                                new_message = await bot.send_message(chat_id=chat_id, text=text)
                            except:
                                pass
                    else:
                        try:
                            new_message = await bot.send_message(chat_id=chat_id, text=text)
                        except telegram.error.BadRequest as ex:
                            if "Not enough rights to send text messages to the chat" in ex.message:
                                try:
                                    error_message = locale.get_string("commands.groups.errors.forbidden.not_enough_rights") \
                                        .replace("[command]", f'<code>/' + command_name + "</code>")

                                    await bot.send_message(
                                        chat_id=user_id,
                                        text=error_message
                                    )
                                except:
                                    pass
                        except:
                            pass
                else:
                    reply_to_message: telegram.Message

                    try:
                        new_message = await reply_to_message.reply_text(text=text)
                    except telegram.error.BadRequest as ex:
                        if "Not enough rights to send text messages to the chat" in ex.message:
                            try:
                                error_message = locale.get_string("commands.groups.errors.forbidden.not_enough_rights") \
                                    .replace("[command]", f'<code>/' + command_name + "</code>")

                                await bot.send_message(
                                    chat_id=user_id,
                                    text=error_message
                                )
                            except:
                                pass
                    except:
                        pass

                if new_message and (cooldown or command_name not in ("dont",)) and \
                        (command_name not in ("hide", "unhide", "move", "addadmin", "rmadmin", "listadmins")
                         or invalid_request is True or update.effective_chat.type in ("group", "supergroup")):
                    async def delete_message(context: ContextTypes.DEFAULT_TYPE) -> None:
                        try:
                            await bot.delete_message(chat_id=message_chat_id, message_id=new_message.message_id)
                        except:
                            pass

                    GlobalVariables.job_queue.run_once(callback=delete_message, when=auto_delete_delay)

            if delete_query_message or \
                    (command_name in ("hide", "unhide", "move", "listadmins")
                     and update.effective_chat.type in ("group", "supergroup")):

                try:
                    await bot.delete_message(chat_id=chat_id, message_id=query_message.message_id)
                except:
                    pass

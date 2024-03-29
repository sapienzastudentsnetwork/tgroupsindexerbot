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
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatMemberAdministrator, ChatMemberOwner
from telegram.ext import ContextTypes

from tgib.data.database import SessionTable, DirectoryTable, AccountTable, ChatTable
from tgib.global_vars import GlobalVariables
from tgib.handlers.queries import Queries
from tgib.i18n.locales import Locale
from tgib.logs import Logger
from tgib.ui.menus import Menus


class Commands:
    command_cooldowns = {"dont": 15, "reload": 15, "userstatus": 60}
    user_last_command_use_dates = {"dont": {}, "reload": {}, "userstatus": {}}
    registered_commands = ["start", "groups", "dont", "userstatus", "reload", "id",
                           "hide", "unhide", "move", "unindex",
                           "addadmin", "rmadmin", "listadmins",
                           "restrict", "unrestrict"]
    private_specific_commands = ("addadmin", "rmadmin", "restrict", "unrestrict")
    group_specific_commands = ("reload",)
    group_admin_commands = ("reload",)
    bot_admin_commands = ("hide", "unhide", "move", "unindex", "restrict", "unrestrict")
    bot_owner_commands = ("addadmin", "rmadmin", "listadmins")
    alias_commands = {"removeadmin": "rmadmin", "bangroup": "hide", "unbangroup": "unhide",
                      "deindex": "unindex", "index": "move", "dontasktoask": "dont",
                      "setadmin": "addadmin", "unsetadmin": "rmadmin", "unadmin": "rmadmin"}

    @classmethod
    async def commands_handler(cls, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        bot_instance  = context.bot
        chat          = update.effective_chat
        chat_id       = chat.id
        user          = update.effective_user
        user_id       = update.effective_user.id
        query_message = update.message

        if query_message.chat.type != "channel":
            bot_username_lower = bot_instance.username.lower()

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
                                              url="tg://resolve?domain=" + GlobalVariables.contact_username)],
                    ]

                    reply_markup = InlineKeyboardMarkup(keyboard)

                    try:
                        new_message = await bot_instance.send_message(chat_id=user_id, text=text, reply_markup=reply_markup)
                    except Exception:
                        new_message = await bot_instance.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)

                        async def delete_message(context: ContextTypes.DEFAULT_TYPE) -> None:
                            try:
                                await bot_instance.delete_message(chat_id=chat_id, message_id=new_message.message_id)
                            except Exception:
                                pass

                        GlobalVariables.job_queue.run_once(callback=delete_message, when=10)

                    try:
                        await bot_instance.delete_message(chat_id=chat_id, message_id=query_message.message_id)
                    except Exception:
                        pass

                return

            texts, text, reply_markup, reply_to_message = [], None, None, None

            user_data, is_user_data = AccountTable.get_account_record(
                user_id,
                create_if_not_existing=(query_message.chat.type == "private")
            )

            user_is_bot_admin = (is_user_data and user_data and user_data["is_admin"])

            cooldown = False

            delete_query_message = True

            delete_answer = None

            delete_answer_delay = 10

            invalid_request = False

            private_chat_priority = False

            bot_owner_chat_id = GlobalVariables.bot_owner

            if not is_user_data and chat.type == "private":
                text, reply_markup = Menus.get_error_menu(locale, source="database")
            else:
                if (is_user_data and Queries.user_can_perform_action(user_data, "/" + command_name)) or (not is_user_data):
                    if command_name == "start":
                        text, reply_markup = Menus.get_main_menu(locale)

                    elif command_name == "groups":
                        text, reply_markup = Queries.explore_category(locale, DirectoryTable.CATEGORIES_ROOT_DIR_ID, user_data)

                    else:
                        if command_name in cls.group_specific_commands and query_message.chat.type == "private":
                            text = locale.get_string("commands.groups.group_specific_command") \
                                .replace("[command]",
                                         f'/<a href="/{command}">' + command_name + "</a>")

                            invalid_request = True

                        elif command_name in cls.private_specific_commands and query_message.chat.type != "private":
                            delete_query_message = False

                            invalid_request = True

                        elif command_name in cls.group_admin_commands and not user_is_bot_admin and not Queries.is_chat_admin(bot_instance, chat_id, user_id):
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

                            elif command_name == "userstatus":
                                private_chat_priority = True

                                delete_answer = False

                                target_user = user
                                target_user_id = user_id

                                third_person = False

                                if chat.type != "private":
                                    third_person = True

                                    if query_message.reply_to_message:
                                        reply_to_message = query_message.reply_to_message

                                        target_user = query_message.reply_to_message.from_user
                                        target_user_id = target_user.id

                                    if not user_is_bot_admin:
                                        if not await Queries.is_chat_admin(bot_instance, chat_id, user_id):
                                            invalid_request = True

                                            text = locale.get_string("commands.userstatus.insufficient_perms")

                                elif len(command_args) > 0 and user_is_bot_admin:
                                    try:
                                        target_user_id = int(command_args[0])

                                        try:
                                            target_user = await bot_instance.get_chat(chat_id=target_user_id)

                                        except:
                                            target_user = None

                                        third_person = True

                                    except:
                                        invalid_request = True

                                        text = locale.get_string("commands.wrong_user_id_format")

                                if not invalid_request:
                                    if third_person:
                                        is_replacement = locale.get_string("commands.userstatus.third_person_is")
                                    else:
                                        is_replacement = locale.get_string("commands.userstatus.second_person_is")

                                    if target_user_id == user_id:
                                        target_user_data = user_data

                                        private_chat_priority = False

                                        delete_answer = True

                                        delete_answer_delay = 20

                                    else:
                                        target_user_data, is_target_user_data = AccountTable.get_account_record(target_user_id, False)

                                    target_info = ""

                                    if target_user_data:
                                        if target_user_id == int(bot_owner_chat_id):
                                            target_info = locale.get_string("commands.userstatus.is_bot_owner")

                                        elif target_user_data["is_admin"]:
                                            target_info = locale.get_string("commands.userstatus.is_a_bot_admin")

                                        elif chat.type != "private" or target_user_id != user_id:
                                            target_info = locale.get_string("commands.userstatus.is_a_bot_user")

                                        if user_is_bot_admin or target_user_id == user_id:
                                            target_can_view_groups   = target_user_data["can_view_groups"]
                                            target_can_add_groups    = target_user_data["can_add_groups"]
                                            target_can_modify_groups = target_user_data["can_modify_groups"]

                                            if (not target_can_view_groups) or (not target_can_add_groups) or (not target_can_modify_groups):
                                                if target_info:
                                                    target_info += "\n\n"

                                                target_info += locale.get_string("commands.userstatus.restrictions_first_line")

                                                if third_person:
                                                    can_replacement = locale.get_string("commands.restrictions.third_person_can")
                                                    possessive_pronoun_replacement = locale.get_string("commands.restrictions.third_person_pronoun")

                                                else:
                                                    can_replacement = locale.get_string("commands.restrictions.second_person_can")
                                                    possessive_pronoun_replacement = locale.get_string("commands.restrictions.second_person_pronoun")

                                                for restriction_key_name in ("can_view_groups", "can_add_groups", "can_modify_groups"):
                                                    if not target_user_data[f"{restriction_key_name}"]:
                                                        target_info += f"\n\n• 🚫 " + locale.get_string(f"commands.restrictions.{restriction_key_name}".replace("can_", "cant_"))\
                                                            .replace("[can]", can_replacement.lower()).replace("[pronoun]", possessive_pronoun_replacement).capitalize()
                                                    else:
                                                        target_info += f"\n\n• " + locale.get_string(f"commands.restrictions.{restriction_key_name}")\
                                                            .replace("[can]", can_replacement).replace("[pronoun]", possessive_pronoun_replacement)

                                    number_of_indexed_chats_is_admin_of, _ = ChatTable.get_total_chats_user_is_admin_of(target_user_id, True)

                                    if number_of_indexed_chats_is_admin_of is not None and number_of_indexed_chats_is_admin_of > 0:
                                        if target_info:
                                            target_info += "\n\n"

                                        target_info += locale.get_string("commands.userstatus.is_admin_of_n_indexed_groups") \
                                            .replace("[n]", str(number_of_indexed_chats_is_admin_of))

                                    if not target_info:
                                        target_info = locale.get_string("commands.userstatus.no_target_data_available")
                                    else:
                                        target_info = target_info.replace("[is]", is_replacement)

                                    target_user_info = f'[<code>{target_user_id}</code>]'

                                    if target_user:
                                        if target_user.username:
                                            target_user_info = f"(@{target_user.username}) {target_user_info}"

                                            if target_user.username == "Matypist":
                                                if locale.lang_code == "it":
                                                    target_info = "💠 [is] il creatore di TGroupsIndexerBot " \
                                                                  "<a href='https://github.com/sapienzastudentsnetwork/" \
                                                                  "tgroupsindexerbot'>[🌐]</a>" + "\n\n" + target_info
                                                else:
                                                    target_info = "💠 [is] the creator of TGroupsIndexerBot " \
                                                                  "<a href='https://github.com/sapienzastudentsnetwork/" \
                                                                  "tgroupsindexerbot'>[🌐]</a>" + "\n\n" + target_info

                                                target_info = target_info.replace("[is]", is_replacement)

                                        if target_user.full_name:
                                            target_user_info = f'<a href="tg://user?id={target_user_id}">{target_user.full_name}</a> {target_user_info}'

                                    text = target_user_info + "\n\n" + target_info

                                    date_str, time_str, offset_str = Queries.get_current_italian_datetime()

                                    text += "\n\n" + locale.get_string("commands.userstatus.generation_date_line") \
                                        .replace("[date]", date_str) \
                                        .replace("[time]", time_str) \
                                        .replace("[offset]", offset_str[1:3])

                            elif command_name == "reload":
                                old_chat_data, new_chat_data, is_new_chat_data = await ChatTable.fetch_chat(bot_instance, chat_id)

                                if is_new_chat_data:
                                    bot_member = await bot_instance.get_chat_member(chat_id, bot_instance.id)

                                    text = locale.get_string("commands.reload.successful")

                                    if not isinstance(bot_member, ChatMemberAdministrator):
                                        text += "\n\n" + locale.get_string("commands.reload.is_not_admin")

                                        delete_answer_delay = 15

                                    elif isinstance(bot_member, ChatMemberAdministrator):
                                        bot_member: ChatMemberAdministrator

                                        if not bot_member.can_invite_users:
                                            try:
                                                chat = await bot_instance.get_chat(chat_id)

                                                chat_permissions = chat.permissions

                                                text += "\n\n"

                                                if chat_permissions.can_invite_users:
                                                    text += locale.get_string("commands.reload.cant_invite_users_via_link")
                                                else:
                                                    text += locale.get_string("commands.reload.cant_add_members")

                                                delete_answer_delay = 15
                                            except Exception:
                                                text = locale.get_string("commands.reload.unsuccessful")

                                    if old_chat_data:
                                        if old_chat_data["hidden_by"] is not None:
                                            text += "\n\n" + locale.get_string("commands.reload.hidden")

                                        elif new_chat_data and not new_chat_data["missing_permissions"]:
                                            if old_chat_data["directory_id"] is not None:
                                                full_target_category_name = DirectoryTable.get_full_category_name(locale.lang_code, old_chat_data["directory_id"])

                                                if full_target_category_name:
                                                    text += "\n\n" + locale.get_string("commands.reload.indexed") \
                                                        .replace("[category]", full_target_category_name)
                                            else:
                                                text += "\n\n" + locale.get_string("commands.reload.not_indexed")

                                else:
                                    text = locale.get_string("commands.reload.unsuccessful")

                            elif command_name in ("hide", "unhide", "move", "unindex"):
                                target_chat_ids = None

                                query_msg_text = query_message.text

                                if update.effective_chat.type in ("group", "supergroup"):
                                    target_chat_ids = [chat_id]

                                else:
                                    if (len(command_args) >= 1
                                        and not (
                                            command_name == "move"
                                            and update.effective_chat.type not in ("group", "supergroup")
                                            and len(command_args) < 2
                                        )
                                    ):
                                        try:
                                            if command_name == "move":
                                                target_chat_ids = [int(chat_id) for chat_id in command_args[:-1]]
                                            else:
                                                target_chat_ids = [int(chat_id) for chat_id in command_args]

                                            # Remove any duplicate ids

                                            seen_chat_ids = set()

                                            unique_target_chat_ids = []

                                            for target_chat_id in target_chat_ids:
                                                if target_chat_id not in seen_chat_ids:
                                                    unique_target_chat_ids.append(target_chat_id)
                                                    seen_chat_ids.add(target_chat_id)

                                            target_chat_ids = unique_target_chat_ids

                                        except Exception:
                                            text = locale.get_string("commands.wrong_chat_id_format")

                                            delete_query_message = False
                                    else:
                                        text = locale.get_string("commands.min_n_args")

                                        if command_name == "move":
                                            text = text.replace("[n]", "2")
                                        else:
                                            text = text.replace("[n]", "1")

                                        invalid_request = True

                                if invalid_request is False and target_chat_ids is not None:
                                    if command_name == "move":
                                        try:
                                            target_directory_id = int(query_msg_text.split(" ")[-1])
                                        except Exception:
                                            text = locale.get_string("commands.wrong_directory_id_format")

                                            delete_query_message = False

                                            invalid_request = True

                                    if invalid_request is False:
                                        for target_chat_id in target_chat_ids:
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

                                                            await Logger.log_chat_action("hide", update.effective_user, target_chat_data)

                                                    else:
                                                        text = locale.get_string("commands.visibility.already_hidden")

                                                elif command_name == "unhide":
                                                    if target_chat_data["hidden_by"] is not None:
                                                        updated = ChatTable.update_chat_visibility(target_chat_id, hidden_by=None)

                                                        if updated:
                                                            if chat_directory_id is not None:
                                                                DirectoryTable.increment_chats_count(chat_directory_id, +1)

                                                            text = locale.get_string("commands.visibility.unhide.successful")

                                                            await Logger.log_chat_action("unhide", update.effective_user, target_chat_data)

                                                    else:
                                                        text = locale.get_string("commands.visibility.already_not_hidden")

                                                elif command_name == "move":
                                                    full_target_category_name = DirectoryTable.get_full_category_name(locale.lang_code, target_directory_id)

                                                    if full_target_category_name is not None:
                                                        if chat_directory_id is None or target_directory_id != chat_directory_id:
                                                            updated = ChatTable.update_chat_directory(target_chat_id, target_directory_id)

                                                            if updated:
                                                                DirectoryTable.increment_chats_count(target_directory_id, +1)

                                                                full_old_category_name = None

                                                                if chat_directory_id is not None:
                                                                    DirectoryTable.increment_chats_count(chat_directory_id, -1)

                                                                    full_old_category_name = DirectoryTable.get_full_category_name(locale.lang_code, chat_directory_id)

                                                                    text = locale.get_string("commands.move.moved") \
                                                                        .replace("[old_category]", str(full_old_category_name))

                                                                else:
                                                                    text = locale.get_string("commands.move.indexed")

                                                                await Logger.log_chat_action(
                                                                    "move", update.effective_user, target_chat_data,
                                                                    new_directory_id=target_directory_id,
                                                                    full_old_category_name=full_old_category_name,
                                                                    full_new_category_name=full_target_category_name
                                                                )

                                                            else:
                                                                text = locale.get_string("commands.directory_database_error")

                                                        else:
                                                            text = locale.get_string("commands.move.already_current_category")

                                                        text = text.replace("[category]", full_target_category_name)

                                                    else:
                                                        text = locale.get_string("commands.directory_database_error")

                                                elif command_name == "unindex":
                                                    if chat_directory_id is not None:
                                                        updated = ChatTable.update_chat_directory(target_chat_id, None)

                                                        if updated:
                                                            DirectoryTable.increment_chats_count(chat_directory_id, -1)

                                                            full_target_category_name = DirectoryTable.get_full_category_name(locale.lang_code, chat_directory_id)

                                                            text = locale.get_string("commands.visibility.unindex.successful") \
                                                                .replace("[category]", str(full_target_category_name))

                                                            await Logger.log_chat_action(
                                                                "unindex", update.effective_user, target_chat_data,
                                                                full_old_category_name=full_target_category_name
                                                            )

                                                    else:
                                                        text = locale.get_string("commands.visibility.already_not_indexed_at_all")

                                                if text:
                                                    text = text.replace("[title]", target_chat_data["title"]).replace("[chat_id]", str(target_chat_id))
                                                else:
                                                    text = locale.get_string("commands.database_error")

                                                    delete_query_message = False

                                                texts.append(text)

                            elif command_name in ("addadmin", "rmadmin", "restrict", "unrestrict"):
                                if len(command_args) >= 1:
                                    if command_name not in ("restrict", "unrestrict") or len(command_args) >= 2:
                                        target_user_id = None

                                        try:
                                            target_user_id = int(command_args[0])

                                        except Exception:
                                            text = locale.get_string("commands.wrong_chat_id_format")

                                            delete_query_message = False

                                        if target_user_id is not None:
                                            target_user_data, is_target_user_data = AccountTable.get_account_record(target_user_id, False)

                                            if is_target_user_data:
                                                updated = False

                                                if command_name == "addadmin":
                                                    if target_user_data["is_admin"] is False:
                                                        updated = AccountTable.update_admin_status(target_user_id, True)

                                                        if updated:
                                                            text = locale.get_string("commands.admins.set")

                                                    else:
                                                        text = locale.get_string("commands.admins.already_admin")

                                                elif command_name == "rmadmin":
                                                    if target_user_data["is_admin"] is True:
                                                        updated = AccountTable.update_admin_status(target_user_id, False)

                                                        if updated:
                                                            text = locale.get_string("commands.admins.unset")

                                                    else:
                                                        text = locale.get_string("commands.admins.already_not_admin")

                                                elif command_name in ("restrict", "unrestrict"):
                                                    restriction_name = ' '.join(command_args[1:])

                                                    can_view_groups_restriction_names = (
                                                        "all", "view", "viewing", "view groups", "viewing groups", "can view groups", "can_view_groups",
                                                        "tutto", "esplora", "esplorare", "esplora gruppi", "esplorare gruppi", "può esplorare gruppi", "può esplorare i gruppi",
                                                        "vedi", "vedere", "vedi gruppi", "vedere gruppi", "può vedere gruppi", "può vedere i gruppi"
                                                    )

                                                    can_add_groups_restriction_names = (
                                                        "all", "add", "adding", "add groups", "adding groups", "can add groups", "can_add_groups",
                                                        "tutto", "aggiungi", "aggiungere", "aggiungi gruppi", "aggiungere gruppi",
                                                        "può aggiungere gruppi", "può aggiungere i gruppi", "può aggiungere un gruppo", "può aggiungere nuovi gruppi"
                                                    )

                                                    can_modify_groups_restriction_names = (
                                                        "all", "modify", "modifying", "modify groups", "modifying groups", "modify groups", "can modify groups", "can_modify_groups",
                                                        "tutto", "modifica", "modificare", "modifica gruppi", "modificare gruppi", "può modificare gruppi", "può modificare i gruppi"
                                                    )

                                                    restriction_names = set(can_view_groups_restriction_names + can_add_groups_restriction_names + can_modify_groups_restriction_names)

                                                    if restriction_name in restriction_names:
                                                        restrictions = {
                                                            "can_view_groups": (restriction_name in can_view_groups_restriction_names),
                                                            "can_add_groups": (restriction_name in can_add_groups_restriction_names),
                                                            "can_modify_groups": (restriction_name in can_modify_groups_restriction_names)
                                                        }

                                                        old_values, new_values = {}, {}

                                                        changes_summary_text = ""

                                                        for restriction_key_name in restrictions.keys():
                                                            restriction_current_value = target_user_data[restriction_key_name]

                                                            old_values[restriction_key_name] = restriction_current_value
                                                            new_values[restriction_key_name] = restriction_current_value

                                                            if restrictions[restriction_key_name]:
                                                                restriction_new_value = not (command_name == "restrict")

                                                                if restriction_current_value != restriction_new_value:
                                                                    new_values[restriction_key_name] = restriction_new_value

                                                                    restriction_descriptive_text = locale.get_string(f"commands.restrictions.{restriction_key_name}")\
                                                                        .replace("[can]", locale.get_string("commands.restrictions.third_person_can"))\
                                                                        .replace("[pronoun]", locale.get_string("commands.restrictions.third_person_pronoun"))

                                                                    changes_summary_text += "\n\n• " \
                                                                        + "<b>" + restriction_descriptive_text + "</b>" \
                                                                        + f": {restriction_current_value} → <u>{restriction_new_value}</u>"

                                                        if changes_summary_text:
                                                            updated = AccountTable.update_account_restrictions(
                                                                chat_id=target_user_id,
                                                                can_view_groups=new_values["can_view_groups"],
                                                                can_add_groups=new_values["can_add_groups"],
                                                                can_modify_groups=new_values["can_modify_groups"],
                                                            )

                                                            if updated:
                                                                try:
                                                                    target_user = await bot_instance.get_chat(chat_id=target_user_id)

                                                                except:
                                                                    target_user = None

                                                                target_user_info = f'[<code>{target_user_id}</code>]'

                                                                if target_user:
                                                                    if target_user.username:
                                                                        target_user_info = f"(@{target_user.username}) {target_user_info}"

                                                                    if target_user.full_name:
                                                                        target_user_info = f'<a href="tg://user?id={target_user_id}">{target_user.full_name}</a> {target_user_info}'

                                                                changes_summary_text += "\n\n🎯 " + target_user_info

                                                                text = locale.get_string("commands.restrictions.updated_first_line") + changes_summary_text

                                                                await Logger.log_user_action(command_name, user, changes_summary_text)
                                                            else:
                                                                text = locale.get_string("commands.database_error")

                                                        else:
                                                            text = locale.get_string("commands.restrictions.no_changes_made")

                                                    else:
                                                        text = locale.get_string("commands.restrictions.wrong_restriction_name")

                                                if text:
                                                    text = text.replace("[chat_id]", str(target_user_id))

                                                if updated:
                                                    delete_query_message = False

                                                elif not text:
                                                    delete_query_message = False

                                                    text = locale.get_string("commands.admins.database_error")

                                            else:
                                                text = locale.get_string("commands.account_database_error")

                                                delete_query_message = False
                                    else:
                                        text = locale.get_string("commands.min_n_args").replace("[n]", "2")

                                        invalid_request = True

                                else:
                                    text = locale.get_string("commands.min_n_args")

                                    if command_name in ("restrict", "unrestrict"):
                                        text = text.replace("[n]", "2")
                                    else:
                                        text = text.replace("[n]", "1")

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
                                                chat = await bot_instance.get_chat(bot_admin_chat_id)
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
                else:
                    text, reply_markup = Menus.get_error_menu(locale, "unauthorized")

                    private_chat_priority = True

            if reply_markup:
                reply_markup = Queries.encode_queries(reply_markup)

            if command_name in ("start", "groups"):
                new_message, error_message = None, None

                try:
                    new_message = await bot_instance.send_message(chat_id=user_id, text=text, reply_markup=reply_markup)

                    if not is_user_data and query_message.chat.type != "private":
                        user_data, is_user_data = AccountTable.get_account_record(user_id, create_if_not_existing=True)

                except telegram.error.Forbidden as ex:
                    if "bot was blocked by the user" in ex.message:
                        error_message = locale.get_string("commands.groups.errors.forbidden.blocked_by_user")
                except telegram.error.BadRequest as ex:
                    if "Chat not found" in ex.message:
                        error_message = locale.get_string("commands.groups.errors.badrequest.chat_not_found")
                except Exception:
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
                        new_message = await bot_instance.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)

                        job_queue = GlobalVariables.job_queue
                        job_queue: telegram.ext.Application.job_queue

                        async def delete_message(context: ContextTypes.DEFAULT_TYPE) -> None:
                            try:
                                await bot_instance.delete_message(chat_id=chat_id, message_id=new_message.message_id)
                            except Exception:
                                pass

                        job_queue.run_once(callback=delete_message, when=10)
                    except Exception:
                        pass

                if is_user_data and not error_message and new_message:
                    old_latest_menu_message_id = SessionTable.get_active_session_menu_message_id(user_id)

                    if old_latest_menu_message_id != -1:
                        if user_id in Queries.user_input_subdirectories_data:
                            await Queries.cancel_categories_operation(locale, bot_instance, user_id)

                        try:
                            await bot_instance.delete_message(chat_id=user_id, message_id=old_latest_menu_message_id)
                        except Exception:
                            pass

                        SessionTable.update_session(user_id, new_message.message_id)
                    else:
                        SessionTable.add_session(user_id, new_message.message_id)

            else:
                if not texts:
                    texts = [text]

                for text in texts:
                    message_chat_id = chat_id

                    new_message = None

                    prioritary_conditions_over_reply_to_message = (private_chat_priority or cooldown or invalid_request)

                    if not private_chat_priority:
                        private_chat_priority = prioritary_conditions_over_reply_to_message or not reply_to_message

                    if private_chat_priority:
                        if prioritary_conditions_over_reply_to_message:
                            try:
                                new_message = await bot_instance.send_message(chat_id=user_id, text=text)

                                message_chat_id = user_id
                            except Exception:
                                try:
                                    new_message = await bot_instance.send_message(chat_id=chat_id, text=text)
                                except Exception:
                                    pass
                        else:
                            try:
                                new_message = await bot_instance.send_message(chat_id=chat_id, text=text)
                            except telegram.error.BadRequest as ex:
                                if "Not enough rights to send text messages to the chat" in ex.message:
                                    try:
                                        error_message = locale.get_string("commands.groups.errors.forbidden.not_enough_rights") \
                                            .replace("[command]", f'<code>/' + command_name + "</code>")

                                        await bot_instance.send_message(
                                            chat_id=user_id,
                                            text=error_message
                                        )
                                    except Exception:
                                        pass
                            except Exception:
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

                                    await bot_instance.send_message(
                                        chat_id=user_id,
                                        text=error_message
                                    )
                                except Exception:
                                    pass
                        except Exception:
                            pass

                    if delete_answer is None:
                        delete_answer = new_message and (cooldown or command_name not in ("dont",)) and \
                            (command_name not in ("hide", "unhide", "move", "addadmin", "rmadmin", "listadmins", "restrict", "unrestrict", "userstatus")
                             or invalid_request is True or update.effective_chat.type in ("group", "supergroup"))

                    if delete_answer:
                        async def delete_message(context: ContextTypes.DEFAULT_TYPE) -> None:
                            try:
                                await bot_instance.delete_message(chat_id=message_chat_id, message_id=new_message.message_id)
                            except Exception:
                                pass

                        GlobalVariables.job_queue.run_once(callback=delete_message, when=delete_answer_delay)

            if not delete_query_message:
                delete_query_message = (command_name in ("hide", "unhide", "move", "listadmins")
                     and update.effective_chat.type in ("group", "supergroup"))

            if delete_query_message:
                try:
                    await bot_instance.delete_message(chat_id=chat_id, message_id=query_message.message_id)
                except Exception:
                    pass

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

import hashlib
from datetime import datetime

import pytz
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext

from tgib.data.database import DirectoryTable, AccountTable, ChatTable, SessionTable
from tgib.i18n.locales import Locale
from tgib.global_vars import GlobalVariables
from tgib.ui.menus import Menus


class Queries:
    fixed_queries = [
        "refresh_session",
        "explore_categories",
        "main_menu",
        "about_menu",
        "wip_alert",
        "expired_session_about_alert"
    ]

    registered_queries = {}
    registered_hashes  = {}

    fd = "  "

    @classmethod
    def register_query(cls, query_data: str) -> None:
        def md5sum(data: str) -> str:
            m = hashlib.md5()
            m.update(data.encode())
            return m.hexdigest()

        hashed_query_data = md5sum(query_data)

        cls.registered_hashes[hashed_query_data] = query_data
        cls.registered_queries[query_data] = hashed_query_data

    @classmethod
    def register_fixed_queries(cls) -> None:
        for query_data in cls.fixed_queries:
            cls.register_query(query_data)

    @classmethod
    def encode_query_data(cls, query_data: str) -> str:
        if query_data in cls.registered_queries:
            return cls.registered_queries[query_data]
        else:
            return "unregistered query"

    @classmethod
    def decode_query_data(cls, hashed_query_data: str) -> str:
        if hashed_query_data in cls.registered_hashes:
            return cls.registered_hashes[hashed_query_data]
        else:
            return "unrecognized query"

    @classmethod
    def encode_queries(cls, inline_keyboard_markup) -> InlineKeyboardMarkup:
        encoded_inline_keyboard = []

        for row in inline_keyboard_markup.inline_keyboard:
            encoded_inline_keyboard_row = []

            for button in row:
                if isinstance(button, InlineKeyboardButton):
                    if button.callback_data:
                        encoded_inline_keyboard_row.append(
                            InlineKeyboardButton(
                                text=button.text,
                                callback_data=cls.encode_query_data(button.callback_data)
                            )
                        )
                    else:
                        encoded_inline_keyboard_row.append(button)

            if encoded_inline_keyboard_row:
                encoded_inline_keyboard.append(encoded_inline_keyboard_row)

        return InlineKeyboardMarkup(encoded_inline_keyboard)

    @classmethod
    def user_can_perform_action(cls, chat_id: int, action: str):
        user_data = AccountTable.get_account_record(chat_id)

        # TODO: if it is a group visualisation action then check
        #       whether the user has the can_view_groups permission

        # TODO: when the functionality to add and/or modify groups will be
        #       implemented also add a check if the user has respectively
        #       the can_add_groups and can_modify_groups permissions

        return True

    @classmethod
    def explore_category(cls, locale: Locale, directory_id: int) -> (str, InlineKeyboardMarkup):
        directory_data, is_directory_data = DirectoryTable.get_directory_data(directory_id)

        if is_directory_data:
            lang_code = locale.lang_code

            if f"i18n_{lang_code}_name" in directory_data and bool(directory_data[f"i18n_{lang_code}_name"]):
                directory_name = directory_data[f"i18n_{lang_code}_name"]
            else:
                directory_name = directory_data[f"i18n_{Locale.def_lang_code}_name"]

            parent_directory_id = -1

            if "parent_id" in directory_data and bool(directory_data["parent_id"]):
                parent_directory_id = directory_data["parent_id"]
                parent_directory_data, _ = DirectoryTable.get_directory_data(parent_directory_id)

                if f"i18n_{lang_code}_name" in parent_directory_data and bool(parent_directory_data[f"i18n_{lang_code}_name"]):
                    parent_directory_name = parent_directory_data[f"i18n_{lang_code}_name"]
                else:
                    parent_directory_name = parent_directory_data[f"i18n_{Locale.def_lang_code}_name"]

            groups_dict, is_groups_dict = ChatTable.get_chats(directory_id)

            if is_groups_dict:
                groups_dict: dict

                keyboard = []

                sub_directories_data, is_sub_directories_data = DirectoryTable.get_sub_directories(directory_id)

                if is_sub_directories_data:
                    sort_key = f"i18n_{lang_code}_name"
                    sorted_ids_and_values = [(curr_sub_directory_id, curr_sub_directory[sort_key]) for curr_sub_directory_id, curr_sub_directory in sub_directories_data.items()]
                    sorted_ids_and_values.sort(key=lambda x: x[1])
                    sorted_ids = [x[0] for x in sorted_ids_and_values]

                    for curr_sub_directory_id in sorted_ids:
                        curr_sub_directory_data, is_curr_sub_directory_data = DirectoryTable.get_directory_data(curr_sub_directory_id)

                        if is_curr_sub_directory_data:
                            if f"i18n_{lang_code}_name" in curr_sub_directory_data and bool(curr_sub_directory_data[f"i18n_{lang_code}_name"]):
                                curr_sub_directory_name = curr_sub_directory_data[f"i18n_{lang_code}_name"]
                            else:
                                curr_sub_directory_name = curr_sub_directory_data[f"i18n_{Locale.def_lang_code}_name"]

                            curr_sub_directory_callback_data = f"cd{GlobalVariables.queries_fd}{curr_sub_directory_id}"
                            Queries.register_query(curr_sub_directory_callback_data)

                            curr_sub_directory_btn_text = curr_sub_directory_name

                            number_of_groups, is_number_of_groups = ChatTable.get_chat_count(curr_sub_directory_id)
                            if is_number_of_groups:
                                curr_sub_directory_btn_text += f" [{number_of_groups}]"

                            keyboard.append([InlineKeyboardButton(text=curr_sub_directory_btn_text,
                                                                  callback_data=curr_sub_directory_callback_data)])
                else:
                    return Menus.get_database_error_menu(locale)

                if parent_directory_id != -1:
                    text = f"<b>" + parent_directory_name + " > " + directory_name + "</b>\n"

                    back_button_text = locale.get_string("explore_directories.sub_directory.back_btn")
                    back_button_callback_data = f"cd{GlobalVariables.queries_fd}{parent_directory_id}"

                else:
                    text = f"<b>" + directory_data["i18n_it_name"] + "</b>\n"

                    back_button_text = locale.get_string("explore_directories.back_to_menu_btn")
                    back_button_callback_data = f"main_menu"

                Queries.register_query(back_button_callback_data)

                keyboard.append([InlineKeyboardButton(text=back_button_text,
                                                      callback_data=back_button_callback_data)])

                if len(groups_dict) > 0:
                    datetime_now = datetime.now(pytz.timezone('Europe/Rome'))

                    date_str   = datetime_now.strftime("%d/%m/%Y")
                    time_str   = datetime_now.strftime("%H:%M")
                    offset_str = datetime_now.strftime("%z")

                    text += "\n" + locale.get_string("explore_groups.category.generation_date_line")\
                        .replace("[date]",   date_str)\
                        .replace("[time]",   time_str)\
                        .replace("[offset]", offset_str[1:3]) + "\n"

                if len(sub_directories_data) > 0 and len(groups_dict) > 0:
                    text += locale.get_string("explore_groups.category.no_category_groups_line")

                for group_chat_id, group_data_dict in groups_dict.items():
                    group_title = group_data_dict["title"]

                    group_join_url = ""

                    if "custom_link" in group_data_dict and bool(group_data_dict["custom_link"]):
                        group_join_url = group_data_dict["custom_link"]
                    elif "invite_link" in group_data_dict and bool(group_data_dict["invite_link"]):
                        group_join_url = group_data_dict["invite_link"]

                    if group_join_url:
                        text += f"\n• {group_title} <a href='{group_join_url}'>" \
                                + locale.get_string("explore_groups.join_href_text") + "</a>"
                    else:
                        groups_dict.pop(group_chat_id)

                if len(sub_directories_data) > 0:
                    if len(groups_dict) > 0:
                        text += "\n"

                    text += locale.get_string("explore_groups.category.sub_categories_line")

                return text, InlineKeyboardMarkup(keyboard)

        return Menus.get_database_error_menu(locale)

    @classmethod
    def cd_queries_handler(cls, directory_id: int, locale: Locale) -> (str, InlineKeyboardMarkup):
        return Queries.explore_category(locale, directory_id)

    @classmethod
    async def callback_queries_handler(cls, update: Update, context: CallbackContext):
        bot           = context.bot
        query         = update.callback_query
        chat_id       = update.effective_chat.id
        query_message = query.message

        locale = Locale(update.effective_user.language_code)

        if query_message.chat.type == "private":
            hashed_query_data = query.data
            query_data = cls.decode_query_data(hashed_query_data)

            text, reply_markup = "", None

            if Queries.user_can_perform_action(chat_id, query_data):
                if query_data in ("refresh_session", "unrecognized query"):
                    query_data = "main_menu"

                if query_data == "explore_categories":
                    text, reply_markup = cls.cd_queries_handler(DirectoryTable.CATEGORIES_ROOT_DIR_ID, locale)

                elif query_data.startswith("cd  "):
                    directory_id = -1

                    try:
                        directory_id = int(query_data[len("cd  "):])
                    except:
                        pass

                    if directory_id != -1:
                        text, reply_markup = cls.cd_queries_handler(directory_id, locale)

                elif query_data == "main_menu":
                    text, reply_markup = Menus.get_main_menu(locale)

                elif query_data == "about_menu":
                    text, reply_markup = Menus.get_about_menu(locale)

                elif query_data == "wip_alert":
                    await query.answer(text=locale.get_string("wip_alert"), show_alert=True)

                elif query_data == "expired_session_about_alert":
                    await query.answer(text=locale.get_string("expired_session_menu.about_alert"), show_alert=True)

            if text or reply_markup:
                reply_markup = Queries.encode_queries(reply_markup)

                await query.answer()

                try:
                    await query_message.edit_text(text=text, reply_markup=reply_markup)
                except:
                    query_message = await bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)

                    if chat_id in SessionTable.active_chat_sessions:
                        SessionTable.update_session(chat_id=chat_id, new_latest_menu_message_id=query_message.message_id)

                if chat_id not in SessionTable.active_chat_sessions:
                    SessionTable.add_session(chat_id=chat_id, latest_menu_message_id=query_message.message_id)

        else:
            try:
                await bot.delete_message(chat_id=chat_id, message_id=query_message.message_id)
            except:
                pass

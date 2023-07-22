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
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatMember, Bot, ChatMemberAdministrator, ChatMemberOwner, User
from telegram.ext import CallbackContext, ContextTypes

from tgib.data.database import DirectoryTable, AccountTable, ChatTable, SessionTable
from tgib.i18n.locales import Locale
from tgib.global_vars import GlobalVariables
from tgib.logs import Logger
from tgib.ui.menus import Menus


class Queries:
    fixed_queries = [
        "refresh_session",
        "explore_categories",
        "main_menu",
        "add_group_menu",
        "about_menu",
        "wip_alert",
        "expired_session_about_alert"
    ]

    registered_queries = {}
    registered_hashes  = {}

    fd = "  "

    user_input_subdirectories_data: dict = {}

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
    async def is_chat_admin(cls, bot, chat_id, user_id) -> (bool | None):
        try:
            chat_member = await bot.get_chat_member(chat_id, user_id)
            return chat_member.status in (ChatMember.OWNER, ChatMember.ADMINISTRATOR)
        except Exception:
            return None

    @classmethod
    def get_current_italian_datetime(cls) -> (str, str, str):
        datetime_now = datetime.now(pytz.timezone('Europe/Rome'))

        date_str = datetime_now.strftime("%d/%m/%Y")
        time_str = datetime_now.strftime("%H:%M:%S")
        offset_str = datetime_now.strftime("%z")

        return date_str, time_str, offset_str

    @classmethod
    def user_can_perform_action(cls, user_data: dict, action: str):
        is_admin          = user_data["is_admin"]
        can_view_groups   = user_data["can_view_groups"]
        can_add_groups    = user_data["can_add_groups"]
        can_modify_groups = user_data["can_modify_groups"]

        if not can_view_groups and action in ("explore_categories", "/groups", "cd"):
            return False

        elif not can_add_groups and (action in ("add_group_menu",)
                                     or action.startswith("hidden_chat_menu")
                                     or action.startswith("missing_permissions_menu")):
            return False

        elif not can_modify_groups and (action in ("/reload",)):
            return False

        # N.B.: checking for bot admin permissions for bot admin commands
        #       is handled by Commands.commands_handler itself

        elif not is_admin:
            admin_required_queries = (
                "create_subdirectory_in", "edit_directory_names",
                "manage_directory", "hide_directory", "unhide_directory",
                "delete_directory", "delete_root_directory", "delete_nonempty_directory"
            )

            for admin_required_query in admin_required_queries:
                if action.startswith(admin_required_query):
                    return False

        return True

    @classmethod
    async def hidden_chat_menu(cls, locale: Locale, chat_id: int, directory_id: int, offset: int) -> (str, InlineKeyboardMarkup):
        chat_data, is_chat_data = ChatTable.get_chat_data(chat_id)

        if is_chat_data:
            if chat_data["hidden_by"] is not None:
                text = locale.get_string("hidden_by_menu.text")

            else:
                text = locale.get_string("hidden_by_menu.alt_text")

            text = text.replace("[title]", chat_data["title"]).replace("[chat_id]", str(chat_id))

        else:
            return Menus.get_error_menu(locale, "database")

        back_button_callback_data = f"index_group_in{cls.fd}{directory_id}{cls.fd}{offset}"
        Queries.register_query(back_button_callback_data)

        keyboard = [
            [InlineKeyboardButton(
                text=locale.get_string("missing_permissions_menu.contact_us_btn"),
                url="tg://resolve?domain=" + GlobalVariables.contact_username
            )],

            [InlineKeyboardButton(
                text=locale.get_string("missing_permissions_menu.back_btn"),
                callback_data=back_button_callback_data
            )]
        ]

        return text, InlineKeyboardMarkup(keyboard)

    @classmethod
    async def missing_permissions_menu(cls, locale: Locale, bot: Bot, chat_id: int, directory_id: int, offset: int) -> (str, InlineKeyboardMarkup):
        try:
            chat = await bot.get_chat(chat_id)

            bot_member = await bot.get_chat_member(chat_id, bot.id)

            text = locale.get_string("missing_permissions_menu.text").replace("[title]", chat.title)

            fixed = False

            if not isinstance(bot_member, ChatMemberAdministrator):
                text += "\n\n" + locale.get_string("missing_permissions_menu.is_not_admin")

            elif isinstance(bot_member, ChatMemberAdministrator):
                bot_member: ChatMemberAdministrator

                if not bot_member.can_invite_users:
                    chat_permissions = chat.permissions

                    text += "\n\n"

                    if chat_permissions.can_invite_users:
                        text += locale.get_string("missing_permissions_menu.cant_invite_users_via_link")
                    else:
                        text += locale.get_string("missing_permissions_menu.cant_add_members")
                else:
                    await ChatTable.fetch_chat(bot, chat_id)

                    text = locale.get_string("missing_permissions_menu.alt_text").replace("[title]", chat.title)

                    fixed = True

            text += "\n\n"

            if not fixed:
                text += locale.get_string("missing_permissions_menu.fix_then_try_again")
            else:
                text += locale.get_string("missing_permissions_menu.already_fixed_try_again")

        except Exception:
            text = locale.get_string("missing_permissions_menu.cant_get_group_info")

        back_button_callback_data = f"index_group_in{cls.fd}{directory_id}{cls.fd}{offset}"
        Queries.register_query(back_button_callback_data)

        keyboard = [
            [InlineKeyboardButton(
                text=locale.get_string("missing_permissions_menu.contact_us_btn"),
                url="tg://resolve?domain=" + GlobalVariables.contact_username
            )],

            [InlineKeyboardButton(
                text=locale.get_string("missing_permissions_menu.back_btn"),
                callback_data=back_button_callback_data
            )]
        ]

        return text, InlineKeyboardMarkup(keyboard)

    @classmethod
    def index_group_in_directory_menu(cls, locale: Locale, directory_id: int, offset: int, user_data: dict) -> (str, InlineKeyboardMarkup):
        chats_per_page = 8

        user_id = user_data["chat_id"]

        number_of_chats_user_is_admin_of, is_number_of_chats_user_is_admin_of = ChatTable.get_total_chats_user_is_admin_of(user_id)

        if is_number_of_chats_user_is_admin_of:
            chats_user_is_admin_of, is_chats_user_is_admin_of = ChatTable.get_chats_user_is_admin_of(user_id, offset, chats_per_page)
            chats_user_is_admin_of: dict

            if is_chats_user_is_admin_of:
                text = locale.get_string("index_group_menu.text")

                keyboard = []

                pages_keyboard = []

                pn = offset + 1

                if offset > 0:
                    previous_page_callback_data = f"index_group_in{cls.fd}{directory_id}{cls.fd}{offset-1}"
                    Queries.register_query(previous_page_callback_data)

                    pages_keyboard.append(
                        InlineKeyboardButton(
                            text="⬅️ " + locale.get_string("index_group_menu.page_btn").replace("[n]", str(pn - 1)),
                            callback_data=previous_page_callback_data
                        )
                    )

                if number_of_chats_user_is_admin_of > (pn * chats_per_page):
                    next_page_callback_data = f"index_group_in{cls.fd}{directory_id}{cls.fd}{offset+1}"
                    Queries.register_query(next_page_callback_data)

                    pages_keyboard.append(
                        InlineKeyboardButton(
                            text=locale.get_string("index_group_menu.page_btn").replace("[n]", str(pn + 1)) + " ➡️",
                            callback_data=next_page_callback_data
                        )
                    )

                if pages_keyboard:
                    keyboard.append(pages_keyboard)

                if len(chats_user_is_admin_of) > 0:
                    for curr_chat_id, curr_chat_data in chats_user_is_admin_of.items():
                        curr_chat_btn_text = curr_chat_data["title"]

                        if curr_chat_data["hidden_by"] is not None:
                            curr_chat_btn_text += " 🚫"

                            curr_chat_callback_data = f"hidden_chat_menu{cls.fd}{curr_chat_id}{cls.fd}{directory_id}{cls.fd}{offset}"

                        elif curr_chat_data["missing_permissions"] is True:
                            curr_chat_btn_text += " ⛔️"

                            curr_chat_callback_data = f"missing_permissions_menu{cls.fd}{curr_chat_id}{cls.fd}{directory_id}{cls.fd}{offset}"

                        elif curr_chat_data["directory_id"] == directory_id:
                            curr_chat_btn_text += " ☑️"

                            curr_chat_callback_data = f"unindex_confirm_menu{cls.fd}{curr_chat_id}{cls.fd}{directory_id}{cls.fd}{offset}"

                        else:
                            curr_chat_callback_data = f"index_confirm_menu{cls.fd}{curr_chat_id}{cls.fd}{directory_id}{cls.fd}{offset}"

                        Queries.register_query(curr_chat_callback_data)

                        keyboard.append(
                            [InlineKeyboardButton(text=curr_chat_btn_text,
                                                  callback_data=curr_chat_callback_data)]
                        )

                    date_str, time_str, offset_str = cls.get_current_italian_datetime()

                    text += "\n\n" + locale.get_string("index_group_menu.generation_date_line") \
                        .replace("[date]", date_str) \
                        .replace("[time]", time_str) \
                        .replace("[offset]", offset_str[1:3]) + "\n"
                else:
                    text += "\n\n" + locale.get_string("index_group_menu.no_groups_available")


                back_button_callback_data = f"cd{cls.fd}{directory_id}"
                Queries.register_query(back_button_callback_data)

                keyboard += [
                    [InlineKeyboardButton(
                        text=locale.get_string("index_group_menu.refresh_btn"),
                        callback_data=f"index_group_in{cls.fd}{directory_id}{cls.fd}{offset}")
                    ],

                    [InlineKeyboardButton(
                        text=locale.get_string("index_group_menu.add_bot_to_group_btn"),
                        url="https://t.me/" + GlobalVariables.bot_instance.username + "?startgroup=start")
                    ],

                    [InlineKeyboardButton(
                        text=locale.get_string("index_group_menu.contact_us_btn"),
                        url="tg://resolve?domain=" + GlobalVariables.contact_username
                    )],

                    [InlineKeyboardButton(
                        text=locale.get_string("index_group_menu.back_btn"),
                        callback_data=back_button_callback_data
                    )]
                ]

                return text, InlineKeyboardMarkup(keyboard)

            else:
                return Menus.get_error_menu(locale, "database")
        else:
            return Menus.get_error_menu(locale, "database")

    @classmethod
    def create_subdirectory_menu(cls, locale: Locale, chat_id: int, parent_directory_id: int):
        input_subdirectory_data = {"i18n_en_name": None, "i18n_it_name": None, "parent_id": parent_directory_id}

        text = locale.get_string("create_subdirectory.ask_for_i18n_en_name")

        back_callback_data = f"cd{cls.fd}" + str(input_subdirectory_data["parent_id"])

        Queries.register_query(back_callback_data)

        keyboard = [[
            InlineKeyboardButton(
                text=locale.get_string("create_subdirectory.undo_btn"),
                callback_data=back_callback_data
            )
        ]]

        cls.user_input_subdirectories_data[chat_id] = input_subdirectory_data

        return text, InlineKeyboardMarkup(keyboard)

    @classmethod
    def edit_directory_names_menu(cls, locale: Locale, chat_id: int, directory_id: int):
        input_subdirectory_data = {"id": directory_id, "i18n_en_name": None, "i18n_it_name": None}

        directory_data, is_directory_data = DirectoryTable.get_directory_data(directory_id)

        if is_directory_data:
            input_subdirectory_data["old_i18n_en_name"] = directory_data["i18n_en_name"]
            input_subdirectory_data["old_i18n_it_name"] = directory_data["i18n_it_name"]

            if directory_data["parent_id"] is not None:
                input_subdirectory_data["parent_id"] = directory_data["parent_id"]
            else:
                input_subdirectory_data["parent_id"] = directory_id

            text = locale.get_string("edit_directory_names.ask_for_new_i18n_en_name") + "\n\n" \
                   + locale.get_string("edit_directory_names.current_value")\
                       .replace(f"[current_value]", directory_data["i18n_en_name"])

            cls.user_input_subdirectories_data[chat_id] = input_subdirectory_data
        else:
            text = locale.get_string("edit_directory_names.cant_get_directory_info")

        back_callback_data = f"cd{cls.fd}" + str(input_subdirectory_data["parent_id"])

        Queries.register_query(back_callback_data)

        keyboard = [[
            InlineKeyboardButton(
                text=locale.get_string("edit_directory_names.undo_btn"),
                callback_data=back_callback_data
            )
        ]]

        return text, InlineKeyboardMarkup(keyboard)

    @classmethod
    async def index_group_menu(cls, locale: Locale, bot: Bot, user: User, chat_id: int, new_directory_id: int = None, offset: int = 0, requires_confirmation: bool = True, unindex_directory_id: int = None, user_can_add_groups: bool = True, user_can_modify_groups: bool = True) -> (str, InlineKeyboardMarkup):
        user_id = user.id

        if new_directory_id is None and unindex_directory_id is None:
            return Menus.get_error_menu(locale, "query")

        if unindex_directory_id is None:
            back_directory_id = new_directory_id
        else:
            back_directory_id = unindex_directory_id

        text = ""

        keyboard = []

        undo_btn = False

        try:
            chat_member = await bot.get_chat_member(chat_id, user_id)

            if chat_member.status in (ChatMember.OWNER, ChatMember.ADMINISTRATOR):
                chat_member: ChatMemberOwner

                if isinstance(chat_member, ChatMemberOwner) or chat_member.can_change_info:
                    chat_data, is_chat_data = ChatTable.get_chat_data(chat_id)

                    if is_chat_data:
                        old_directory_id = None

                        if chat_data["directory_id"] is not None:
                            old_directory_id = chat_data["directory_id"]

                        valid_request = True

                        user_lang_code = locale.lang_code

                        if new_directory_id is not None:
                            full_category_name = DirectoryTable.get_full_category_name(user_lang_code, new_directory_id)
                        else:
                            full_category_name = DirectoryTable.get_full_category_name(user_lang_code, old_directory_id)

                        if new_directory_id is None:
                            if old_directory_id is None:
                                text = locale.get_string("index_group_error.already_not_indexed_at_all") \
                                    .replace("[title]", chat_data["title"])

                                valid_request = False

                            elif old_directory_id != unindex_directory_id:
                                text = locale.get_string("index_group_error.already_not_indexed_there") \
                                    .replace("[title]", chat_data["title"]) \
                                    .replace("[category]", full_category_name)

                                valid_request = False

                        if chat_data["hidden_by"] is not None:
                            return await cls.hidden_chat_menu(locale, chat_id, back_directory_id, offset)

                        if valid_request:
                            if old_directory_id is None or old_directory_id != new_directory_id:
                                if requires_confirmation:
                                    chat = await bot.get_chat(chat_id)

                                    if new_directory_id is not None:
                                        text = locale.get_string("index_group_confirm_menu.text")

                                        confirm_button_callback_data = f"index{cls.fd}{chat_id}{cls.fd}{new_directory_id}{cls.fd}{offset}"

                                    else:
                                        text = locale.get_string("unindex_group_confirm_menu.text")

                                        confirm_button_callback_data = f"unindex{cls.fd}{chat_id}{cls.fd}{unindex_directory_id}{cls.fd}{offset}"

                                    text = text.replace("[title]", chat.title).replace("[category]", str(full_category_name))

                                    if new_directory_id is not None and old_directory_id is not None:
                                        full_old_category_name = DirectoryTable.get_full_category_name(user_lang_code, old_directory_id)

                                        text += "\n\n" + locale.get_string("index_group_confirm_menu.will_be_moved") \
                                            .replace("[current_category]", full_old_category_name)

                                    if chat_member.status != ChatMember.OWNER:
                                        text += "\n\n" + locale.get_string("index_group_confirm_menu.owner_will_be_alerted")

                                    Queries.register_query(confirm_button_callback_data)

                                    keyboard.append(
                                        [InlineKeyboardButton(
                                            text=locale.get_string("index_group_confirm_menu.confirm_btn"),
                                            callback_data=confirm_button_callback_data
                                        )]
                                    )

                                    undo_btn = True

                                else:
                                    unauthorized = False

                                    if new_directory_id is not None:
                                        if old_directory_id is not None:
                                            if not user_can_modify_groups:
                                                unauthorized = True
                                        elif not user_can_add_groups:
                                            unauthorized = True
                                    elif not user_can_modify_groups:
                                        unauthorized = True

                                    if unauthorized:
                                        return Menus.get_error_menu(locale, "unauthorized")

                                    updated = ChatTable.update_chat_directory(chat_id, new_directory_id)

                                    if updated:
                                        if new_directory_id is not None:
                                            full_old_category_name = None

                                            if old_directory_id is not None:
                                                DirectoryTable.increment_chats_count(old_directory_id, -1)

                                            DirectoryTable.increment_chats_count(new_directory_id, +1)

                                            if old_directory_id is not None:
                                                full_old_category_name = DirectoryTable.get_full_category_name(user_lang_code, old_directory_id)

                                                text = locale.get_string("index_group.moved") \
                                                    .replace("[old_category]", full_old_category_name)

                                                await Logger.log_chat_action(
                                                    "index", user, chat_data, new_directory_id,
                                                    full_old_category_name=full_old_category_name,
                                                    full_new_category_name=full_category_name
                                                )

                                            else:
                                                text = locale.get_string("index_group.indexed")

                                                await Logger.log_chat_action(
                                                    "index", user, chat_data, new_directory_id,
                                                    full_new_category_name=full_category_name
                                                )

                                        else:
                                            old_directory_id: int

                                            DirectoryTable.increment_chats_count(old_directory_id, -1)

                                            text = locale.get_string("unindex_group.successful")

                                            # await Logger.log_chat_action("unindex", user, chat_data,
                                            #                              full_old_category_name=full_category_name)

                                        text = text.replace("[title]", chat_data["title"]) \
                                            .replace("[category]", str(full_category_name))

                                    else:
                                        return Menus.get_error_menu(locale, "database")

                            else:
                                text = locale.get_string("index_group.error.already_current_category") \
                                    .replace("[title]", chat_data["title"]) \
                                    .replace("[category]", str(full_category_name))

                    else:
                        return Menus.get_error_menu(locale, "database")

                else:
                    text = locale.get_string("index_group.change_group_info_permission_required")

            else:
                text = locale.get_string("index_group.error.admin_required")

        except Exception as ex:
            if new_directory_id is not None:
                Logger.log("exception", "Queries.index_group_menu",
                           f"An exception occurred while handling a index query"
                           f" of '{chat_id}', by '{user_id}', to '{new_directory_id}'", ex)
            else:
                Logger.log("exception", "Queries.index_group_menu",
                           f"An exception occurred while handling a unindex query"
                           f" of '{chat_id}', by '{user_id}', from '{unindex_directory_id}'", ex)

            text = locale.get_string("index_group.error.cant_get_group_info")

        back_button_callback_data = f"index_group_in{cls.fd}{back_directory_id}{cls.fd}{offset}"
        Queries.register_query(back_button_callback_data)

        if undo_btn:
            keyboard.append(
                [InlineKeyboardButton(
                    text=locale.get_string("index_group_confirm_menu.undo_btn"),
                    callback_data=back_button_callback_data
                )]
            )

        else:
            keyboard.append(
                [InlineKeyboardButton(
                    text=locale.get_string("index_group_confirm_menu.back_btn"),
                    callback_data=back_button_callback_data
                )]
            )

        return text, InlineKeyboardMarkup(keyboard)

    @classmethod
    def explore_category(cls, locale: Locale, directory_id: int, user_data: dict) -> (str, InlineKeyboardMarkup):
        directory_data, is_directory_data = DirectoryTable.get_directory_data(directory_id)

        if not is_directory_data and directory_id == DirectoryTable.CATEGORIES_ROOT_DIR_ID:
            inserted_id, is_inserted_id = DirectoryTable.create_directory("Groups", "Gruppi", DirectoryTable.CATEGORIES_ROOT_DIR_ID, None)

            if is_inserted_id:
                directory_data, is_directory_data = DirectoryTable.get_directory_data(inserted_id)

        if is_directory_data:
            user_is_bot_admin = user_data["is_admin"]

            if directory_data["hidden_by"] is None or user_data["is_admin"]:
                lang_code = locale.lang_code

                directory_name = DirectoryTable.get_directory_localized_name(lang_code, directory_data)

                parent_directory_id = -1

                if "parent_id" in directory_data and bool(directory_data["parent_id"]):
                    parent_directory_id = directory_data["parent_id"]

                user_id = user_data["chat_id"]
                user_can_add_groups = user_data["can_add_groups"]
                user_can_modify_groups = user_data["can_modify_groups"]

                groups_dict, is_groups_dict = ChatTable.get_directory_indexed_chats(
                    directory_id,
                    skip_missing_permissions_chats=not user_is_bot_admin,
                    skip_hidden_chats=not user_is_bot_admin,
                    user_id=user_id
                )

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

                            if is_curr_sub_directory_data and (not curr_sub_directory_data["hidden_by"] or user_is_bot_admin):
                                if f"i18n_{lang_code}_name" in curr_sub_directory_data and bool(curr_sub_directory_data[f"i18n_{lang_code}_name"]):
                                    curr_sub_directory_name = curr_sub_directory_data[f"i18n_{lang_code}_name"]
                                elif f"i18n_{Locale.def_lang_code}_name" in curr_sub_directory_data and bool(curr_sub_directory_data[f"i18n_{Locale.def_lang_code}_name"]):
                                    curr_sub_directory_name = curr_sub_directory_data[f"i18n_{Locale.def_lang_code}_name"]
                                else:
                                    curr_sub_directory_name = curr_sub_directory_id

                                curr_sub_directory_callback_data = f"cd{cls.fd}{curr_sub_directory_id}"
                                Queries.register_query(curr_sub_directory_callback_data)

                                curr_sub_directory_btn_text = curr_sub_directory_name

                                if not curr_sub_directory_data["hidden_by"]:
                                    number_of_groups, is_number_of_groups = DirectoryTable.get_chats_count(curr_sub_directory_id)
                                    if is_number_of_groups:
                                        curr_sub_directory_btn_text += f" [{number_of_groups}]"
                                else:
                                    curr_sub_directory_btn_text = "🥷 " + curr_sub_directory_btn_text

                                keyboard.append([InlineKeyboardButton(text=curr_sub_directory_btn_text,
                                                                      callback_data=curr_sub_directory_callback_data)])
                    else:
                        return Menus.get_error_menu(locale)

                    if user_can_add_groups or user_can_modify_groups:
                        index_group_here_button_text = locale.get_string("explore_directories.index_group_here_btn")

                        index_group_here_callback_data = f"index_group_in{cls.fd}{directory_id}{cls.fd}0"
                        Queries.register_query(index_group_here_callback_data)

                        keyboard.append([InlineKeyboardButton(text=index_group_here_button_text,
                                                              callback_data=index_group_here_callback_data)])

                    if user_is_bot_admin:
                        create_subdirectory_button_text = locale.get_string("explore_directories.create_subdirectory_here_btn")
                        create_subdirectory_button_callback_data = f"create_subdirectory_in{cls.fd}{directory_id}"

                        Queries.register_query(create_subdirectory_button_callback_data)

                        keyboard.append([InlineKeyboardButton(text=create_subdirectory_button_text,
                                                              callback_data=create_subdirectory_button_callback_data)])

                        manage_directory_menu_button_text = locale.get_string("explore_directories.manage_directory_btn")
                        manage_directory_menu_button_callback_data = f"manage_directory{cls.fd}{directory_id}"

                        Queries.register_query(manage_directory_menu_button_callback_data)

                        keyboard.append([InlineKeyboardButton(text=manage_directory_menu_button_text,
                                                              callback_data=manage_directory_menu_button_callback_data)])

                    category_description = None

                    if parent_directory_id != -1:
                        category_description = DirectoryTable.get_full_category_name(lang_code, directory_id)

                    if category_description:
                        text = f"📂 <b>" + category_description + "</b>\n"

                    else:
                        text = f"📁 <b>" + directory_name + "</b>\n"


                    if parent_directory_id != -1:
                        back_button_text = locale.get_string("explore_directories.sub_directory.back_btn")
                        back_button_callback_data = f"cd{cls.fd}{parent_directory_id}"

                    else:
                        back_button_text = locale.get_string("explore_directories.back_to_menu_btn")
                        back_button_callback_data = f"main_menu"

                    Queries.register_query(back_button_callback_data)

                    keyboard.append([InlineKeyboardButton(text=back_button_text,
                                                          callback_data=back_button_callback_data)])

                    if user_is_bot_admin:
                        text += f"\n🆔 <code>{directory_id}</code>"

                        if parent_directory_id != -1:
                            text += f" [<code>{parent_directory_id}</code>]"

                        text += "\n"

                    if len(groups_dict) > 0:
                        date_str, time_str, offset_str = cls.get_current_italian_datetime()

                        text += "\n" + locale.get_string("explore_groups.category.generation_date_line")\
                            .replace("[date]",   date_str)\
                            .replace("[time]",   time_str)\
                            .replace("[offset]", offset_str[1:3]) + "\n"
                    elif len(sub_directories_data) == 0:
                        text += "\n" + locale.get_string("explore_groups.category.no_groups")

                    if len(sub_directories_data) > 0 and len(groups_dict) > 0:
                        text += locale.get_string("explore_groups.category.no_category_groups_line")

                    listed_groups = 0

                    for group_chat_id, group_data_dict in groups_dict.items():
                        group_title = group_data_dict["title"]

                        group_join_url = ""

                        if "custom_link" in group_data_dict and bool(group_data_dict["custom_link"]):
                            group_join_url = group_data_dict["custom_link"]
                        elif "invite_link" in group_data_dict and bool(group_data_dict["invite_link"]):
                            group_join_url = group_data_dict["invite_link"]

                        if "hidden_by" in group_data_dict and bool(group_data_dict["hidden_by"]):
                            bullet_char = "🚫"
                        elif "missing_permissions" in group_data_dict and bool(group_data_dict["missing_permissions"]):
                            bullet_char = "⛔️"
                        else:
                            bullet_char = "•"

                        if group_join_url:
                            text += f"\n{bullet_char} {group_title} <a href='{group_join_url}'>" \
                                    + locale.get_string("explore_groups.join_href_text") + "</a>"

                            if user_is_bot_admin:
                                text += " {<code>" + str(group_chat_id) + "</code>}"

                            listed_groups += 1

                    if len(sub_directories_data) > 0:
                        if listed_groups > 0:
                            text += "\n"

                        text += locale.get_string("explore_groups.category.sub_categories_line")

                    return text, InlineKeyboardMarkup(keyboard)

        text, reply_markup = Menus.get_error_menu(locale, "database")

        text = locale.get_string("explore_groups.cant_access_category")

        return text, reply_markup

    @classmethod
    async def manage_directory_menu(cls, locale: Locale, directory_data: dict) -> (str, InlineKeyboardMarkup):
        directory_id = directory_data["id"]

        text = await DirectoryTable.get_directory_data_summary(directory_data, locale)

        edit_callback_data = f"edit_directory_names{cls.fd}{directory_id}"
        Queries.register_query(edit_callback_data)

        keyboard = [
            [InlineKeyboardButton(
                text=locale.get_string("manage_directory.edit_directory_names_btn"),
                callback_data=edit_callback_data
            )]
        ]

        if directory_data["hidden_by"]:
            unhide_callback_data = f"unhide_directory{cls.fd}{directory_id}"
            Queries.register_query(unhide_callback_data)

            keyboard.append(
                [
                    InlineKeyboardButton(
                        text=locale.get_string("manage_directory.unhide_directory_btn"),
                        callback_data=unhide_callback_data
                    )
                ]
            )

        else:
            hide_callback_data = f"hide_directory{cls.fd}{directory_id}"
            Queries.register_query(hide_callback_data)

            keyboard.append(
                [
                    InlineKeyboardButton(
                        text=locale.get_string("manage_directory.hide_directory_btn"),
                        callback_data=hide_callback_data
                    )
                ]
            )

        if directory_data["parent_id"] is None:
            delete_btn_text = locale.get_string("manage_directory.delete_root_directory_btn")
            delete_btn_callback_data = f"delete_root_directory{cls.fd}{directory_id}"
            Queries.register_query(delete_btn_callback_data)

        elif DirectoryTable.directory_is_empty(directory_id):
            delete_btn_text = locale.get_string("manage_directory.delete_directory_btn")
            delete_btn_callback_data = f"delete_directory_confirm_menu{cls.fd}{directory_id}"
            Queries.register_query(delete_btn_callback_data)

        else:
            delete_btn_text = locale.get_string("manage_directory.delete_nonempty_directory_btn")
            delete_btn_callback_data = f"delete_nonempty_directory{cls.fd}{directory_id}"
            Queries.register_query(delete_btn_callback_data)

        keyboard.append(
            [
                InlineKeyboardButton(
                    text=delete_btn_text,
                    callback_data=delete_btn_callback_data
                )
            ]
        )

        back_callback_data = f"cd{cls.fd}{directory_id}"
        Queries.register_query(back_callback_data)

        keyboard.append(
            [
                InlineKeyboardButton(
                    text=locale.get_string("manage_directory.back_btn"),
                    callback_data=back_callback_data
                )
            ]
        )

        return text, InlineKeyboardMarkup(keyboard)

    @classmethod
    def back_to_manage_directory_menu(cls, locale: Locale, directory_id: int, text: str) -> (str, InlineKeyboardMarkup):
        back_callback_data = f"manage_directory{cls.fd}{directory_id}"
        Queries.register_query(back_callback_data)

        keyboard = [
            [InlineKeyboardButton(
                text=locale.get_string("manage_directory.back_btn"),
                callback_data=back_callback_data
            )]
        ]

        return text, InlineKeyboardMarkup(keyboard)

    @classmethod
    def cd_queries_handler(cls, directory_id: int, locale: Locale, user_data: dict) -> (str, InlineKeyboardMarkup):
        return Queries.explore_category(locale, directory_id, user_data)

    @classmethod
    async def cancel_categories_operation(cls, locale: Locale, bot: Bot, user_id: int):
        if user_id in cls.user_input_subdirectories_data:
            if "id" in cls.user_input_subdirectories_data[user_id]:
                operation_canceled_string = locale.get_string("edit_directory_names.canceled")
            else:
                operation_canceled_string = locale.get_string("create_subdirectory.canceled")

            cls.user_input_subdirectories_data[user_id] = {}
            cls.user_input_subdirectories_data.pop(user_id)

            try:
                operation_canceled_message = await bot.send_message(chat_id=user_id, text=operation_canceled_string)

                async def delete_message(context: ContextTypes.DEFAULT_TYPE) -> None:
                    try:
                        await bot.delete_message(chat_id=user_id, message_id=operation_canceled_message.message_id)
                    except Exception:
                        pass

                GlobalVariables.job_queue.run_once(callback=delete_message, when=5)

            except Exception:
                pass

    @classmethod
    async def callback_queries_handler(cls, update: Update, context: CallbackContext):
        bot           = context.bot
        query         = update.callback_query
        user          = update.effective_user
        user_id       = user.id
        query_message = query.message

        locale = Locale(user.language_code)

        if query_message.chat.type == "private":
            hashed_query_data = query.data
            query_data = cls.decode_query_data(hashed_query_data)

            query_args = query_data.split(cls.fd)[1:]

            text, reply_markup = "", None

            user_data, is_user_data = AccountTable.get_account_record(user_id)

            if is_user_data:
                if Queries.user_can_perform_action(user_data, query_data):
                    try:
                        if user_id in cls.user_input_subdirectories_data:
                            await cls.cancel_categories_operation(locale, bot, user_id)

                        if query_data in ("refresh_session", "unrecognized query"):
                            query_data = "main_menu"

                        if query_data == "explore_categories":
                            text, reply_markup = cls.cd_queries_handler(DirectoryTable.CATEGORIES_ROOT_DIR_ID, locale, user_data)

                        elif query_data.startswith(f"cd{cls.fd}"):
                            target_directory_id = int(query_args[0])

                            text, reply_markup = cls.cd_queries_handler(target_directory_id, locale, user_data)

                        elif query_data.startswith(f"manage_directory{cls.fd}") \
                                or query_data.startswith(f"hide_directory{cls.fd}") \
                                or query_data.startswith(f"unhide_directory{cls.fd}") \
                                or query_data.startswith(f"delete_directory{cls.fd}") \
                                or query_data.startswith(f"delete_directory_confirm_menu{cls.fd}") \
                                or query_data.startswith(f"delete_root_directory{cls.fd}") \
                                or query_data.startswith(f"delete_nonempty_directory{cls.fd}"):

                            target_directory_id = int(query_args[0])

                            target_directory_data, is_target_directory_data = DirectoryTable.get_directory_data(target_directory_id)

                            if is_target_directory_data:
                                old_target_directory_data = dict(target_directory_data)

                                parent_target_directory_id = target_directory_data["parent_id"]

                                updated = None

                                if query_data.startswith(f"manage_directory{cls.fd}"):
                                    text, reply_markup = await cls.manage_directory_menu(locale, target_directory_data)

                                elif query_data.startswith(f"hide_directory{cls.fd}") or query_data.startswith(f"unhide_directory{cls.fd}"):
                                    if target_directory_data["hidden_by"]:
                                        if query_data.startswith(f"unhide_directory{cls.fd}"):
                                            updated = DirectoryTable.update_directory_visibility(target_directory_id, None)

                                        else:
                                            text = locale.get_string("hide_directory.already_hidden")

                                    else:
                                        if query_data.startswith(f"hide_directory{cls.fd}"):
                                            updated = DirectoryTable.update_directory_visibility(target_directory_id, user_id)

                                        else:
                                            text = locale.get_string("unhide_directory.already_visible")

                                    if updated:
                                        chats_count, is_chats_count = DirectoryTable.get_chats_count(target_directory_id, False, True)

                                        if is_chats_count and chats_count > 0:
                                            if query_data.startswith(f"hide_directory{cls.fd}"):
                                                DirectoryTable.increment_chats_count(target_directory_id, -chats_count)
                                            elif parent_target_directory_id is not None:
                                                DirectoryTable.increment_chats_count(parent_target_directory_id, chats_count)

                                        text, reply_markup = await cls.manage_directory_menu(locale, target_directory_data)

                                        await Logger.log_directory_visibility_action(
                                            action=query_data[:query_data.rfind(cls.fd)].replace("_", " "),
                                            admin=user,
                                            directory_data_summary=await DirectoryTable.get_directory_data_summary(
                                                old_target_directory_data, locale
                                            )
                                        )

                                elif query_data.startswith(f"delete_directory{cls.fd}") \
                                        or query_data.startswith(f"delete_directory_confirm_menu{cls.fd}") \
                                        or query_data.startswith(f"delete_root_directory{cls.fd}") \
                                        or query_data.startswith(f"delete_nonempty_directory{cls.fd}"):

                                    if parent_target_directory_id:
                                        if not query_data.startswith(f"delete_root_directory{cls.fd}"):
                                            if DirectoryTable.directory_is_empty(target_directory_id):
                                                if not query_data.startswith(f"delete_nonempty_directory{cls.fd}"):
                                                    if not query_data.startswith(f"delete_directory_confirm_menu{cls.fd}"):
                                                        updated = DirectoryTable.delete_directory(target_directory_id)

                                                        if updated:
                                                            old_directory_data_summary = await DirectoryTable.get_directory_data_summary(
                                                                old_target_directory_data,
                                                                locale
                                                            )

                                                            text = locale.get_string("delete_directory.deleted_first_line")

                                                            text += "\n\n" + old_directory_data_summary

                                                            back_callback_data = f"cd{cls.fd}{parent_target_directory_id}"
                                                            Queries.register_query(back_callback_data)

                                                            keyboard = [
                                                                [InlineKeyboardButton(
                                                                    text=locale.get_string("delete_directory.back_btn"),
                                                                    callback_data=back_callback_data
                                                                )]
                                                            ]

                                                            reply_markup = InlineKeyboardMarkup(keyboard)

                                                            await Logger.log_directory_visibility_action(
                                                                action="DELETE DIRECTORY",
                                                                admin=user,
                                                                directory_data_summary=old_directory_data_summary
                                                            )
                                                    else:
                                                        old_directory_data_summary = await DirectoryTable.get_directory_data_summary(
                                                            old_target_directory_data,
                                                            locale
                                                        )

                                                        text = locale.get_string("delete_directory.confirm_menu.text")

                                                        text += "\n\n" + old_directory_data_summary

                                                        confirm_button_callback_data = f"delete_directory{cls.fd}{target_directory_id}"
                                                        Queries.register_query(confirm_button_callback_data)

                                                        back_button_callback_data = f"manage_directory{cls.fd}{target_directory_id}"
                                                        Queries.register_query(back_button_callback_data)

                                                        keyboard = [
                                                            [
                                                                InlineKeyboardButton(
                                                                    text=locale.get_string("delete_directory.confirm_menu.confirm_btn"),
                                                                    callback_data=confirm_button_callback_data
                                                                )
                                                            ],

                                                            [
                                                                InlineKeyboardButton(
                                                                    text=locale.get_string("delete_directory.confirm_menu.undo_btn"),
                                                                    callback_data=back_button_callback_data
                                                                )
                                                            ]
                                                        ]

                                                        reply_markup = InlineKeyboardMarkup(keyboard)
                                                else:
                                                    text = locale.get_string("delete_directory.cant_delete_nonempty_directory") \
                                                           + "\n\n" + locale.get_string("delete_directory.no_longer_nonempty_directory")

                                            else:
                                                text = locale.get_string("delete_directory.cant_delete_nonempty_directory")
                                        else:
                                            text = locale.get_string("delete_directory.cant_delete_root_directory") \
                                                   + "\n\n" + locale.get_string("delete_directory.no_longer_root_directory")
                                    else:
                                        text = locale.get_string("delete_directory.cant_delete_root_directory")

                                if not text:
                                    text, reply_markup = Menus.get_error_menu(locale, "database")

                                elif not reply_markup:
                                    text, reply_markup = cls.back_to_manage_directory_menu(locale, target_directory_id, text)

                            else:
                                text, reply_markup = Menus.get_error_menu(locale, "database")

                                text = locale.get_string("manage_directory.database_error")

                        elif query_data == "main_menu":
                            text, reply_markup = Menus.get_main_menu(locale)

                        elif query_data == "add_group_menu":
                            text, reply_markup = Menus.get_add_group_menu(locale, bot.username)

                        elif query_data == "about_menu":
                            text, reply_markup = Menus.get_about_menu(locale)

                        elif query_data.startswith(f"index_group_in{cls.fd}"):
                            target_directory_id = int(query_args[0])

                            offset = int(query_args[1])

                            text, reply_markup = cls.index_group_in_directory_menu(locale, target_directory_id, offset, user_data)

                        elif query_data.startswith(f"create_subdirectory_in{cls.fd}"):
                            parent_directory_id = int(query_args[0])

                            text, reply_markup = cls.create_subdirectory_menu(locale, user_id, parent_directory_id)

                        elif query_data.startswith(f"edit_directory_names{cls.fd}"):
                            directory_id = int(query_args[0])

                            text, reply_markup = cls.edit_directory_names_menu(locale, user_id, directory_id)

                        elif query_data.startswith(f"missing_permissions_menu{cls.fd}") \
                                or query_data.startswith(f"hidden_chat_menu{cls.fd}") \
                                or query_data.startswith(f"index_confirm_menu{cls.fd}") \
                                or query_data.startswith(f"index{cls.fd}") \
                                or query_data.startswith(f"unindex_confirm_menu{cls.fd}") \
                                or query_data.startswith(f"unindex{cls.fd}"):

                            target_chat_id = int(query_args[0])

                            target_directory_id = int(query_args[1])

                            offset = int(query_args[2])

                            user_can_add_groups = user_data["can_add_groups"]
                            user_can_modify_groups = user_data["can_modify_groups"]

                            if query_data.startswith(f"missing_permissions_menu{cls.fd}"):
                                text, reply_markup = await cls.missing_permissions_menu(locale, bot,
                                                                                        target_chat_id, target_directory_id, offset)

                            elif query_data.startswith(f"hidden_chat_menu{cls.fd}"):
                                text, reply_markup = await cls.hidden_chat_menu(locale, target_chat_id, target_directory_id, offset)

                            elif query_data.startswith(f"index_confirm_menu{cls.fd}"):
                                text, reply_markup = await cls.index_group_menu(locale, bot,
                                                                                user, target_chat_id, target_directory_id, offset,
                                                                                requires_confirmation=True,
                                                                                user_can_add_groups=user_can_add_groups,
                                                                                user_can_modify_groups=user_can_modify_groups)

                            elif query_data.startswith(f"index{cls.fd}"):
                                text, reply_markup = await cls.index_group_menu(locale, bot,
                                                                                user, target_chat_id, target_directory_id, offset,
                                                                                requires_confirmation=False,
                                                                                user_can_add_groups=user_can_add_groups,
                                                                                user_can_modify_groups=user_can_modify_groups)

                            elif query_data.startswith(f"unindex_confirm_menu{cls.fd}"):
                                text, reply_markup = await cls.index_group_menu(locale, bot,
                                                                                user, target_chat_id, None, offset,
                                                                                requires_confirmation=True,
                                                                                unindex_directory_id=target_directory_id,
                                                                                user_can_add_groups=user_can_add_groups,
                                                                                user_can_modify_groups=user_can_modify_groups)

                            elif query_data.startswith(f"unindex{cls.fd}"):
                                text, reply_markup = await cls.index_group_menu(locale, bot,
                                                                                user, target_chat_id, None, offset,
                                                                                requires_confirmation=False,
                                                                                unindex_directory_id=target_directory_id,
                                                                                user_can_add_groups=user_can_add_groups,
                                                                                user_can_modify_groups=user_can_modify_groups)

                        elif query_data == "wip_alert":
                            await query.answer(text=locale.get_string("wip_alert"), show_alert=True)

                        elif query_data == "expired_session_about_alert":
                            await query.answer(text=locale.get_string("expired_session_menu.about_alert"), show_alert=True)

                    except Exception as ex:
                        Logger.log("exception", "Queries.callback_queries_handler",
                                   f"An exception occurred while handling query '{query_data}' from '{user_id}'", ex)

                        text, reply_markup = Menus.get_error_menu(locale, "query")
                else:
                    text, reply_markup = Menus.get_error_menu(locale, "unauthorized")
            else:
                text, reply_markup = Menus.get_error_menu(locale)

            if text or reply_markup:
                edit_message_id = query_message.message_id

                if user_id in SessionTable.active_chat_sessions and SessionTable.active_chat_sessions[user_id] != query_message.id:
                    edit_message_id = SessionTable.active_chat_sessions[user_id]

                    try:
                        await bot.delete_message(chat_id=user_id, message_id=query_message.message_id)

                    except Exception:
                        pass

                reply_markup = Queries.encode_queries(reply_markup)

                await query.answer()

                edited = False

                new_message_id = edit_message_id

                try:
                    await bot.edit_message_text(text=text, chat_id=user_id, message_id=edit_message_id, reply_markup=reply_markup)

                    edited = True

                except Exception:
                    new_message = await bot.send_message(chat_id=user_id, text=text, reply_markup=reply_markup)

                    new_message_id = new_message.message_id

                    if user_id in SessionTable.active_chat_sessions:
                        SessionTable.update_session(chat_id=user_id, new_latest_menu_message_id=new_message_id)

                    try:
                        await bot.delete_message(chat_id=user_id, message_id=edit_message_id)
                    except Exception:
                        pass

                if user_id not in SessionTable.active_chat_sessions:
                    SessionTable.add_session(chat_id=user_id, latest_menu_message_id=new_message_id)

        else:
            try:
                await bot.delete_message(chat_id=user_id, message_id=query_message.message_id)
            except Exception:
                pass

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

from telegram import Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext

from tgib.data.database import AccountTable, DirectoryTable, SessionTable
from tgib.handlers.queries import Queries
from tgib.i18n.locales import Locale
from tgib.logs import Logger
from tgib.ui.menus import Menus


class Messages:
    @classmethod
    async def text_messages_handler(cls, update: Update, context: CallbackContext):
        message = update.message
        chat = update.effective_chat

        if not message or chat.type != "private":
            return False

        user = update.effective_user
        chat_id = user.id

        user_data, is_user_data = AccountTable.get_account_record(chat_id, False)

        if not is_user_data:
            return False

        if chat_id not in Queries.user_input_subdirectories_data:
            return False

        locale = Locale(user.language_code)

        if chat_id in Queries.user_input_subdirectories_data and user_data["is_admin"]:
            adding_categories_data = Queries.user_input_subdirectories_data[chat_id]

            input_value = message.text

            if len(input_value) > 100:
                await message.reply_text(locale.get_string("add_category.error.too_long_input"))

                return False

            key_name = None

            if adding_categories_data["i18n_en_name"] is None:
                key_name = "i18n_en_name"

            elif adding_categories_data["i18n_it_name"] is None:
                key_name = "i18n_it_name"

            else:
                # It should never happen, but just in case...

                Queries.user_input_subdirectories_data[chat_id] = {}

                Queries.user_input_subdirectories_data.pop(chat_id)

                return False

            Queries.user_input_subdirectories_data[chat_id][key_name] = input_value

            new_message_text = None

            new_keyboard = []

            editing = ("id" in Queries.user_input_subdirectories_data[chat_id])

            if not editing:
                back_callback_data = f"cd{Queries.fd}" + str(adding_categories_data["parent_id"])
            else:
                back_callback_data = f"cd{Queries.fd}" + str(adding_categories_data["id"])

            Queries.register_query(back_callback_data)

            updated = False

            if key_name == "i18n_en_name":
                if not editing:
                    new_message_text = locale.get_string("add_category.ask_for_i18n_it_name")
                else:
                    new_message_text = locale.get_string("edit_category.ask_for_new_i18n_it_name")

                new_message_text = new_message_text.replace("[i18n_en_name]", input_value)

                if "parent_directory_id" in adding_categories_data:
                    new_message_text += "\n\n" + locale.get_string("edit_category.current_value") \
                        .replace(f"[current_value]", adding_categories_data[f"old_{key_name}"])

                if not editing:
                    new_keyboard.append([
                        InlineKeyboardButton(
                            text=locale.get_string("add_category.undo_btn"),
                            callback_data=back_callback_data
                        )
                    ])

                else:
                    new_keyboard.append([
                        InlineKeyboardButton(
                            text=locale.get_string("edit_category.undo_btn"),
                            callback_data=back_callback_data
                        )
                    ])

            else:
                no_changes_made = False

                if not editing:
                    i18n_en_name = adding_categories_data["i18n_en_name"]
                    i18n_it_name = input_value

                    new_i18n_en_name = i18n_en_name
                    new_i18n_it_name = i18n_it_name

                    directory_id, updated = DirectoryTable.create_directory(
                        i18n_en_name=i18n_en_name,
                        i18n_it_name=i18n_it_name,
                        directory_id=None,
                        parent_directory_id=adding_categories_data["parent_id"]
                    )

                    if updated:
                        new_message_text = locale.get_string("add_category.successful_menu.first_line")
                    else:
                        new_message_text = locale.get_string("add_category.database_error")

                else:
                    directory_id = adding_categories_data["id"]
                    i18n_en_name = adding_categories_data["old_i18n_en_name"]
                    i18n_it_name = adding_categories_data["old_i18n_it_name"]

                    new_i18n_en_name = adding_categories_data["i18n_en_name"]
                    new_i18n_it_name = input_value

                    if new_i18n_en_name != i18n_en_name or new_i18n_it_name != i18n_it_name:
                        updated = DirectoryTable.update_directory_names(
                            id=adding_categories_data["id"],
                            new_i18n_en_name=new_i18n_en_name,
                            new_i18n_it_name=new_i18n_it_name
                        )

                        if updated:
                            new_message_text = locale.get_string("edit_category.successful_menu.first_line")
                        else:
                            new_message_text = locale.get_string("edit_category.database_error")
                    else:
                        new_message_text = locale.get_string("edit_category.no_changes_made")

                        updated = True

                        no_changes_made = True

                if updated:
                    if not editing or not no_changes_made:
                        new_message_text += f"\n\n🆔 {directory_id}"

                        new_message_text += f"\n\n🇮🇹 {i18n_it_name}"

                        if editing and new_i18n_it_name != i18n_it_name:
                            new_message_text += f"\n      ↪️ {new_i18n_it_name}"

                        new_message_text += f"\n\n🇬🇧 {i18n_en_name}"

                        if editing and new_i18n_en_name != i18n_en_name:
                            new_message_text += f"\n      ↪️ {new_i18n_en_name}"

                        parent_directory_id = adding_categories_data["parent_id"]

                        parent_directory_name = str(
                            DirectoryTable.get_full_category_name(locale.lang_code, parent_directory_id))

                        if parent_directory_id != directory_id:
                            parent_directory_name_symbol = "📍"

                            if editing:
                                parent_directory_name_symbol = "📁"

                            new_message_text += f"\n\n{parent_directory_name_symbol} {parent_directory_name} [<code>{parent_directory_id}</code>]"

                    new_keyboard = []

                    if not editing:
                        new_keyboard.append([
                            InlineKeyboardButton(
                                text=locale.get_string("add_category.successful_menu.back_btn"),
                                callback_data=back_callback_data
                            )
                        ])

                        await Logger.log_directory_action(
                            action="create directory",
                            admin=user,
                            directory_id=directory_id,
                            i18n_it_name=i18n_it_name,
                            i18n_en_name=i18n_en_name,
                            parent_directory_id=parent_directory_id,
                            parent_directory_name=parent_directory_name
                        )

                    else:
                        new_keyboard.append([
                            InlineKeyboardButton(
                                text=locale.get_string("edit_category.successful_menu.back_btn"),
                                callback_data=back_callback_data
                            )
                        ])

                        if not no_changes_made:
                            await Logger.log_directory_action(
                                action="edit directory",
                                admin=user,
                                directory_id=directory_id,
                                i18n_it_name=i18n_it_name,
                                i18n_en_name=i18n_en_name,
                                parent_directory_id=parent_directory_id,
                                parent_directory_name=parent_directory_name,
                                new_i18n_it_name=new_i18n_it_name,
                                new_i18n_en_name=new_i18n_en_name
                            )

                    Queries.user_input_subdirectories_data[chat_id] = {}

                    Queries.user_input_subdirectories_data.pop(chat_id)

            new_reply_markup = InlineKeyboardMarkup(new_keyboard)

        else:
            new_message_text, new_reply_markup = Menus.get_error_menu(locale, "unauthorized")

            Queries.user_input_subdirectories_data[chat_id] = {}

            Queries.user_input_subdirectories_data.pop(chat_id)

        bot_instance: Bot = context.bot

        new_reply_markup = Queries.encode_queries(new_reply_markup)

        new_message_id = SessionTable.get_active_session_menu_message_id(chat_id)

        try:
            await bot_instance.edit_message_text(text=new_message_text, chat_id=chat_id, message_id=new_message_id, reply_markup=new_reply_markup)

        except Exception:
            try:
                new_message = await bot_instance.send_message(chat_id=chat_id, text=new_message_text, reply_markup=new_reply_markup)

                new_message_id = new_message.message_id

                if chat_id in SessionTable.active_chat_sessions:
                    SessionTable.update_session(chat_id, new_message_id)
                else:
                    SessionTable.add_session(chat_id, new_message_id)

            except Exception as ex:
                Logger.log("exception", "Messages.text_messages",
                           f"An exception occurred while sending message to '{chat_id}'", ex)

        try:
            await bot_instance.delete_message(chat_id=chat_id, message_id=message.message_id)
        except Exception:
            pass

        return True

import hashlib

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext

from ssb.data.database import CategoriesTable, AccountTable, ChatTable, SessionTable
from ssb.i18n.locales import Locale
from ssb.settings import Settings
from ssb.ui.menus import Menus


class Queries:
    fixed_queries = [
        "cd",
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

        return True

    @classmethod
    def get_categories(cls, locale: Locale) -> (str, InlineKeyboardMarkup):
        text     = locale.get_string("explore_groups.choose_category")
        keyboard = []

        categories_names, is_categories_names = CategoriesTable.get_categories()

        if is_categories_names:
            categories_names = sorted(categories_names)

            for main_category_name in categories_names:
                category_callback_data = f"cd{Settings.queries_fd}" + main_category_name

                Queries.register_query(category_callback_data)

                number_of_groups = ChatTable.get_number_of_groups(main_category_name)

                keyboard.append([InlineKeyboardButton(text=f"{main_category_name} [{number_of_groups}]",
                                                      callback_data=category_callback_data)])

            keyboard.append([InlineKeyboardButton(text=locale.get_string("explore_groups.choose_category.back_btn"),
                                                  callback_data="main_menu")])

            return text, InlineKeyboardMarkup(keyboard)

        else:
            return Menus.get_database_error_menu(locale)

    @classmethod
    def explore_category(cls, locale: Locale, main_category_name: str, sub_category_name: str = None) -> (str, InlineKeyboardMarkup):
        sub_categories_names = {}

        if sub_category_name:
            groups_dict, is_groups_dict = ChatTable.get_groups(main_category_name, sub_category_name)

            text = f"<b>{main_category_name} > {sub_category_name}</b>\n"

            back_button_text = locale.get_string("explore_groups.sub_category.back_btn")
            back_button_callback_data = f"cd{Settings.queries_fd}{main_category_name}"

        else:
            groups_dict, is_groups_dict = ChatTable.get_groups(main_category_name)

            text = f"<b>{main_category_name}</b>\n"

            if len(groups_dict) > 0:
                text += locale.get_string("explore_groups.category.no_category_groups_line")

            back_button_callback_data = f"cd"

            back_button_text = locale.get_string("explore_groups.category.back_btn")

        if is_groups_dict:
            keyboard = []

            if not sub_category_name:
                sub_categories_names, is_subcategories_names = CategoriesTable.get_sub_categories(main_category_name)

                if is_subcategories_names:
                    sub_categories_names = sorted(sub_categories_names)

                    for curr_sub_category_name in sub_categories_names:
                        sub_category_callback_data = f"cd{Settings.queries_fd}{main_category_name}{Settings.queries_fd}{curr_sub_category_name}"

                        Queries.register_query(sub_category_callback_data)

                        number_of_groups = ChatTable.get_number_of_groups(main_category_name, curr_sub_category_name)

                        keyboard.append([InlineKeyboardButton(text=f"{curr_sub_category_name} [{number_of_groups}]",
                                                              callback_data=sub_category_callback_data)])
                else:
                    return Menus.get_database_error_menu(locale)

            keyboard.append([InlineKeyboardButton(text=back_button_text,
                                                  callback_data=back_button_callback_data)])

            for group_chat_id, group_data_dict in groups_dict.items():
                group_title       = group_data_dict["title"]
                group_invite_link = group_data_dict["invite_link"]

                text += f"\n• {group_title} <a href='{group_invite_link}'>" \
                        + locale.get_string("explore_groups.join_href_text") + "</a>"

            if not sub_category_name and len(sub_categories_names) > 0:
                if len(groups_dict) > 0:
                    text += "\n"

                text += locale.get_string("explore_groups.category.sub_categories_line")

            return text, InlineKeyboardMarkup(keyboard)
        else:
            return Menus.get_database_error_menu(locale)

    @classmethod
    def cd_queries_handler(cls, query_data: str, locale: Locale) -> (str, InlineKeyboardMarkup):
        fields = query_data.split("  ")

        number_of_fields = len(fields)

        if number_of_fields > 0:
            main_category = fields[0]

            sub_category = None
            if number_of_fields > 1:
                sub_category = fields[1]

            return Queries.explore_category(locale, main_category, sub_category)

        return None, None

    @classmethod
    async def callback_queries_handler(cls, update: Update, context: CallbackContext):
        bot           = context.bot
        query         = update.callback_query
        chat_id       = update.effective_chat.id
        query_message = query.message

        locale = Locale(update.effective_user.language_code)

        if query_message.chat.type == "private":
            hashed_query_data = query.data
            query_data        = cls.decode_query_data(hashed_query_data)

            text, reply_markup = "", None

            if Queries.user_can_perform_action(chat_id, query_data):
                if query_data == "unrecognized query":
                    query_data = "main_menu"

                if query_data.startswith("cd  "):
                    text, reply_markup = cls.cd_queries_handler(query_data[len("cd  "):], locale)

                elif query_data == "cd":
                    text, reply_markup = Queries.get_categories(locale)

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
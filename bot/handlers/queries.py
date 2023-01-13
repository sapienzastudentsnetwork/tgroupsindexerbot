import hashlib

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext

from bot.database.data import Database
from bot.i18n.locales import Locale
from bot.settings import Settings
from bot.ui.menus import Menus


class Queries:
    fixed_queries = [
        "main_menu",
        "about_menu",
        "wip"
    ]

    registered_queries = {}
    registered_hashes  = {}

    fd = "  "

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
    def get_categories(cls, locale: Locale) -> (str, InlineKeyboardMarkup):
        text     = locale.get_string("explore_groups.choose_category")
        keyboard = []

        for category_name in Database.data_structure.keys():
            category_callback_data = f"cd{Settings.queries_fd}" + category_name

            number_of_groups = Database.data_structure[category_name]["number_of_groups"]

            keyboard.append([InlineKeyboardButton(text=f"{category_name} [{number_of_groups}]",
                                                  callback_data=cls.encode_query_data(category_callback_data))])

        keyboard.append([InlineKeyboardButton(text=locale.get_string("explore_groups.choose_category.back_btn"),
                                              callback_data=cls.encode_query_data("main_menu"))])

        return text, InlineKeyboardMarkup(keyboard)

    @classmethod
    def get_groups(cls, locale: Locale, main_category_name: str, sub_category_name: str = None) -> (str, InlineKeyboardMarkup):
        if sub_category_name:
            text = f"<b>{main_category_name} > {sub_category_name}</b>\n"

            back_button_text = locale.get_string("explore_groups.sub_category.back_btn")
            back_button_callback_data = f"cd{Settings.queries_fd}{main_category_name}"

            groups_dict = Database.data_structure[main_category_name]["sub_categories"][sub_category_name]["groups"]
        else:
            text = f"<b>{main_category_name}</b>\n"

            if len(Database.data_structure[main_category_name]["groups"].keys()) > 0:
                text += locale.get_string("explore_groups.category.no_category_groups_line")

            back_button_callback_data = f"cd"

            back_button_text = locale.get_string("explore_groups.category.back_btn")
            groups_dict = Database.data_structure[main_category_name]["groups"]

        keyboard = []

        if not sub_category_name:
            for curr_sub_category_name in Database.data_structure[main_category_name]["sub_categories"].keys():
                sub_category_callback_data = f"cd{Settings.queries_fd}{main_category_name}{Settings.queries_fd}{curr_sub_category_name}"

                number_of_groups = Database.data_structure[main_category_name]["sub_categories"][curr_sub_category_name]["number_of_groups"]

                keyboard.append([InlineKeyboardButton(text=f"{curr_sub_category_name} [{number_of_groups}]",
                                                      callback_data=cls.encode_query_data(sub_category_callback_data))])

        keyboard.append([InlineKeyboardButton(text=back_button_text,
                                              callback_data=cls.encode_query_data(back_button_callback_data))])

        for group_title, group_data_dict in groups_dict.items():
            text += f"\n• {group_title} <a href='" + group_data_dict["invite_link"] + "'>" \
                    + locale.get_string("explore_groups.join_href_text") + "</a>"

        if not sub_category_name and len(Database.data_structure[main_category_name]["sub_categories"].keys()) > 0:
            if len(Database.data_structure[main_category_name]["groups"].keys()) > 0:
                text += "\n"

            text += locale.get_string("explore_groups.category.sub_categories_line")

        return text, InlineKeyboardMarkup(keyboard)

    @classmethod
    def cd_queries_handler(cls, query_data: str, locale: Locale) -> (str, InlineKeyboardMarkup):
        fields = query_data.split("  ")

        number_of_fields = len(fields)

        if number_of_fields > 0:
            main_category = fields[0]

            sub_category = None
            if number_of_fields > 1:
                sub_category = fields[1]

            return Queries.get_groups(locale, main_category, sub_category)

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

            if query_data == "unrecognized query":
                query_data = "main_menu"

            print(f"{chat_id} : {query_data}")

            text, reply_markup = "", None

            if query_data.startswith("cd  "):
                text, reply_markup = cls.cd_queries_handler(query_data[len("cd  "):], locale)

            elif query_data == "cd":
                text, reply_markup = Queries.get_categories(locale)

            elif query_data == "main_menu":
                text, reply_markup = Menus.get_main_menu(locale)

            elif query_data == "about_menu":
                text, reply_markup = Menus.get_about_menu(locale)

            elif query_data == "wip":
                await query.answer(text=locale.get_string("wip"))

            if text or reply_markup:
                await query.answer()

                try:
                    await query_message.edit_text(text=text, reply_markup=reply_markup)
                except:
                    await bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)
        else:
            try:
                await bot.delete_message(chat_id=chat_id, message_id=query_message.message_id)
            except:
                pass
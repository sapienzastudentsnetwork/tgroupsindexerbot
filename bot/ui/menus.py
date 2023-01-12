from telegram import InlineKeyboardMarkup, InlineKeyboardButton

from bot.i18n.locales import Locale


class Menus:
    @classmethod
    def get_main_menu(cls, locale: Locale) -> (str, InlineKeyboardMarkup):
        from bot.handlers.queries import Queries

        text = locale.get_string("main_menu.text")

        keyboard = [
            [InlineKeyboardButton(text=locale.get_string("main_menu.explore_groups_btn"),
                                  callback_data=Queries.encode_query_data("cd"))],
            [InlineKeyboardButton(text=locale.get_string("main_menu.adding_groups_guide_btn"),
                                  callback_data=Queries.encode_query_data("wip"))],
            [InlineKeyboardButton(text=locale.get_string("main_menu.about_message_btn"),
                                  callback_data=Queries.encode_query_data("about_menu"))]
        ]

        return text, InlineKeyboardMarkup(keyboard)

    @classmethod
    def get_about_menu(cls, locale: Locale) -> (str, InlineKeyboardMarkup):
        text = locale.get_string("about_menu.text")

        keyboard = [
            [InlineKeyboardButton(text=locale.get_string("about_menu.contact_us"),
                                  url=f'tg://resolve?domain=sapienzastudentsnetworkbot')],
            [InlineKeyboardButton(text=locale.get_string("about_menu.back_btn"),
                                  callback_data="main_menu")]
        ]

        return text, InlineKeyboardMarkup(keyboard)
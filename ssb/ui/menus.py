from telegram import InlineKeyboardMarkup, InlineKeyboardButton

from ssb.global_vars import GlobalVariables
from ssb.i18n.locales import Locale


class Menus:
    @classmethod
    def get_main_menu(cls, locale: Locale) -> (str, InlineKeyboardMarkup):
        text = locale.get_string("main_menu.text")

        keyboard = [
            [InlineKeyboardButton(text=locale.get_string("main_menu.explore_groups_btn"),
                                  callback_data="explore_categories")],
            [InlineKeyboardButton(text=locale.get_string("main_menu.adding_groups_guide_btn"),
                                  callback_data="wip_alert")],
            [InlineKeyboardButton(text=locale.get_string("main_menu.about_message_btn"),
                                  callback_data="about_menu")]
        ]

        return text, InlineKeyboardMarkup(keyboard)

    @classmethod
    def get_about_menu(cls, locale: Locale) -> (str, InlineKeyboardMarkup):
        text = locale.get_string("about_menu.text").replace("[accounts_count]", str(GlobalVariables.stats_accounts_count))

        keyboard = [
            [
             InlineKeyboardButton(text=locale.get_string("about_menu.github_repo_btn"),
                                  url=f'https://github.com/sapienzastudentsnetwork/sapienzastudentsbot'),
             InlineKeyboardButton(text=locale.get_string("about_menu.git_channel_btn"),
                                  url=f'tg://resolve?domain=sapienzastudentsbotgit')],
            [
             InlineKeyboardButton(text=locale.get_string("about_menu.contact_us_btn"),
                                  url=f'tg://resolve?domain=sapienzastudentsnetworkbot'),
             InlineKeyboardButton(text=locale.get_string("about_menu.report_issue_btn"),
                                  url=f'https://github.com/sapienzastudentsnetwork/sapienzastudentsbot/issues/new?'
                                      f'title=[ISSUE]%20Please%20choose%20a%20title%20for%20this%20issue'
                                      f'&body=Please%20describe%20the%20issue%20in%20detail%20here.%20Thanks%20in%20advance%20:)')
            ],
            [InlineKeyboardButton(text=locale.get_string("about_menu.feature_request_btn"),
                                  url=f'https://github.com/sapienzastudentsnetwork/sapienzastudentsbot/issues/new?'
                                      f'title=[FEATURE REQUEST]%20Please%20choose%20a%20title%20for%20this%20feature%20request'
                                      f'&body=Please%20describe%20the%20request%20in%20detail%20here.%20Thanks%20in%20advance%20:)')],
            [InlineKeyboardButton(text=locale.get_string("about_menu.back_btn"),
                                  callback_data="main_menu")]
        ]

        return text, InlineKeyboardMarkup(keyboard)

    @classmethod
    def get_database_error_menu(cls, locale: Locale) -> (str, InlineKeyboardMarkup):
        text = locale.get_string("database_error_menu.text")

        keyboard = [
            [InlineKeyboardButton(text=locale.get_string("database_error_menu.contact_us"),
                                  url=f'tg://resolve?domain=sapienzastudentsnetworkbot')],
            [InlineKeyboardButton(text=locale.get_string("database_error_menu.back_btn"),
                                  callback_data="main_menu")]
        ]

        return text, InlineKeyboardMarkup(keyboard)

    @classmethod
    def get_expired_session_menu(cls) -> (str, InlineKeyboardMarkup):
        locale = Locale(Locale.def_lang_code)

        text = locale.get_string("expired_session_menu.text")

        keyboard = [
            [InlineKeyboardButton(text=locale.get_string("expired_session_menu.about_btn"),
                                  callback_data="expired_session_about_alert")],
            [InlineKeyboardButton(text=locale.get_string("expired_session_menu.back_btn"),
                                  callback_data="refresh_session")]
        ]

        return text, InlineKeyboardMarkup(keyboard)

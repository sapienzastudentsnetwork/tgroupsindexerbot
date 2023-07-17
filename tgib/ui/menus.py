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

from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Bot

from tgib.global_vars import GlobalVariables
from tgib.i18n.locales import Locale


class Menus:
    @classmethod
    def get_main_menu(cls, locale: Locale) -> (str, InlineKeyboardMarkup):
        text = locale.get_string("main_menu.text")

        keyboard = [
            [InlineKeyboardButton(text=locale.get_string("main_menu.explore_groups_btn"),
                                  callback_data="explore_categories")],
            [InlineKeyboardButton(text=locale.get_string("main_menu.add_bot_to_group_btn"),
                                  callback_data="add_group_menu")],
            [InlineKeyboardButton(text=locale.get_string("main_menu.about_message_btn"),
                                  callback_data="about_menu")]
        ]

        return text, InlineKeyboardMarkup(keyboard)

    @classmethod
    def get_add_group_menu(cls, locale: Locale, bot_username: str) -> (str, InlineKeyboardMarkup):
        text = locale.get_string("add_group_menu.text")

        text = text.replace("[bot_username]", "@" + bot_username)

        keyboard = [
            [InlineKeyboardButton(text=locale.get_string("add_group_menu.1_btn"),
                                  url="http://t.me/" + bot_username + "?startgroup=start")],
            [InlineKeyboardButton(text=locale.get_string("add_group_menu.2_btn"),
                                  callback_data="explore_categories")],
            [InlineKeyboardButton(text=locale.get_string("add_group_menu.contact_us_btn"),
                                  url="tg://resolve?domain=" + GlobalVariables.contact_username)],
            [InlineKeyboardButton(text=locale.get_string("add_group_menu.back_btn"),
                                  callback_data="main_menu")]
        ]

        return text, InlineKeyboardMarkup(keyboard)

    @classmethod
    def get_about_menu(cls, locale: Locale) -> (str, InlineKeyboardMarkup):
        sapienzastudentsbot = True

        if GlobalVariables.bot_instance and GlobalVariables.bot_instance.username.lower() == "sapienzastudentsbot":
            sapienzastudentsbot = True

        if sapienzastudentsbot:
            text = locale.get_string("about_menu.sapienzastudentsbot")
        else:
            if locale.lang_code == "it":
                text = '🚀 Creato a partire da TGroupsIndexerBot' \
                       ' <a href="https://github.com/sapienzastudentsnetwork/tgroupsindexerbot">[GitHub]</a> di @Matypist'
            else:
                text = '🚀 Powered by TGroupsIndexerBot' \
                       ' <a href="https://github.com/sapienzastudentsnetwork/tgroupsindexerbot">[GitHub]</a> by @Matypist'

        text = text.replace("[accounts_count]", str(GlobalVariables.stats_accounts_count))

        keyboard = []

        if sapienzastudentsbot:
            keyboard += [
                [
                 InlineKeyboardButton(text=locale.get_string("about_menu.github_repo_btn"),
                                      url=f'https://github.com/sapienzastudentsnetwork/tgroupsindexerbot'),
                 InlineKeyboardButton(text=locale.get_string("about_menu.git_channel_btn"),
                                      url=f'tg://resolve?domain=tgroupsindexerbotgit')
                ],
                [
                 InlineKeyboardButton(text=locale.get_string("about_menu.feature_request_btn"),
                                     url=f'https://github.com/sapienzastudentsnetwork/tgroupsindexerbot/issues/new?'
                                         f'title=[FEATURE REQUEST]%20Please%20choose%20a%20title%20for%20this%20feature%20request'
                                         f'&body=Please%20describe%20the%20request%20in%20detail%20here.%20Thanks%20in%20advance%20:)'),
                 InlineKeyboardButton(text=locale.get_string("about_menu.report_issue_btn"),
                                      url=f'https://github.com/sapienzastudentsnetwork/tgroupsindexerbot/issues/new?'
                                          f'title=[ISSUE]%20Please%20choose%20a%20title%20for%20this%20issue'
                                          f'&body=Please%20describe%20the%20issue%20in%20detail%20here.%20Thanks%20in%20advance%20:)')
                ],
                [
                    InlineKeyboardButton(text=locale.get_string("about_menu.contact_us_btn"),
                                         url=f'tg://resolve?domain=' + GlobalVariables.contact_username),
                ],
            ]

        keyboard.append([InlineKeyboardButton(text=locale.get_string("about_menu.back_btn"), callback_data="main_menu")])

        return text, InlineKeyboardMarkup(keyboard)

    @classmethod
    def get_error_menu(cls, locale: Locale, source: str = "database") -> (str, InlineKeyboardMarkup):
        text = locale.get_string(f"{source}_error_menu.text")

        keyboard = [
            [InlineKeyboardButton(text=locale.get_string(f"{source}_error_menu.contact_us_btn"),
                                  url=f'tg://resolve?domain=' + GlobalVariables.contact_username)],
            [InlineKeyboardButton(text=locale.get_string(f"{source}_error_menu.back_btn"),
                                  callback_data="main_menu")]
        ]

        return text, InlineKeyboardMarkup(keyboard)

    @classmethod
    def get_expired_session_menu(cls) -> (str, InlineKeyboardMarkup):
        locale = Locale(Locale.def_lang_code)

        text = locale.get_string("expired_session_menu.text")

        keyboard = [
            [InlineKeyboardButton(text=locale.get_string("expired_session_menu.refresh_session_btn"),
                                  callback_data="refresh_session")],
            [InlineKeyboardButton(text=locale.get_string("expired_session_menu.about_btn"),
                                  callback_data="expired_session_about_alert")]
        ]

        return text, InlineKeyboardMarkup(keyboard)

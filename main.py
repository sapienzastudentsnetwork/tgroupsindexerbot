#!/usr/bin/env python

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

from os import getenv as os_getenv

import pytz
from telegram import __version__ as tg_ver
from telegram.constants import ParseMode
from telegram.ext import Application, CallbackQueryHandler, Defaults, MessageHandler, filters, ChatMemberHandler

from tgib.data.database import Database, SessionTable, AccountTable, ChatTable
from tgib.global_vars import GlobalVariables
from tgib.handlers.statuschanges import StatusChanges
from tgib.handlers.commands import Commands
from tgib.handlers.queries import Queries
from tgib.i18n.locales import Locale
from tgib.logs import Logger
from tgib.urlooking.github import GitHubMonitor

try:
    from telegram import __version_info__

except ImportError:
    __version_info__ = (0, 0, 0, 0, 0)  # type: ignore[assignment]

if __version_info__ < (20, 0, 0, "alpha", 1):
    raise RuntimeError(
        f"This code is not compatible with your current PTB version {tg_ver}. It requires a version later than v20.0."
    )


def add_application_handlers(application: Application):
    application.add_handlers([
        MessageHandler(filters=filters.StatusUpdate.MIGRATE,
                       callback=StatusChanges.migrate_handler),

        MessageHandler(filters=filters.COMMAND, callback=Commands.commands_handler),

        CallbackQueryHandler(callback=Queries.callback_queries_handler),

        ChatMemberHandler(callback=StatusChanges.my_chat_member_handler,
                          chat_member_types=ChatMemberHandler.MY_CHAT_MEMBER)
    ])


def main() -> None:
    Logger.init_logger(os_getenv("EXCEPTION_LOG_CHAT_ID"), os_getenv("ADMIN_ACTIONS_LOG_CHAT_ID"))

    Locale.init_locales()

    Database.init_db()

    Queries.register_fixed_queries()

    defaults = Defaults(parse_mode=ParseMode.HTML, tzinfo=pytz.timezone('Europe/Rome'), disable_web_page_preview=True)

    application = Application.builder().token(os_getenv("TOKEN")).defaults(defaults).build()
    application: Application

    application.job_queue.run_once(callback=SessionTable.expire_old_sessions, when=0)

    add_application_handlers(application)

    application.job_queue.run_once(callback=ChatTable.fetch_chats, when=0, data=application.bot)

    GitHubMonitor.init(application.bot)

    GlobalVariables.set_accounts_count(AccountTable.get_account_records_count())

    GlobalVariables.bot_owner = os_getenv("OWNER_CHAT_ID")

    GlobalVariables.bot_instance = application.bot

    GlobalVariables.job_queue = application.job_queue

    GlobalVariables.contact_username = os_getenv("CONTACT_USERNAME")

    if not GlobalVariables.contact_username:
        GlobalVariables.contact_username = "username"

    application.job_queue.run_repeating(
        callback=GitHubMonitor.look_for_updates,
        interval=GitHubMonitor.interval,
        first=1
    )

    application.run_polling()


if __name__ == "__main__":
    main()

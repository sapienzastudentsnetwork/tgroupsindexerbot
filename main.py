#!/usr/bin/env python
from os import getenv as os_getenv

import pytz
from telegram import __version__ as tg_ver
from telegram.constants import ParseMode
from telegram.ext import Application, CallbackQueryHandler, Defaults, MessageHandler, filters

from ssb.data.database import Database, SessionTable
from ssb.handlers.commands import Commands
from ssb.handlers.queries import Queries
from ssb.i18n.locales import Locale
from ssb.logs import Logger
from ssb.urlooking.github import GitHubMonitor

try:
    from telegram import __version_info__

except ImportError:
    __version_info__ = (0, 0, 0, 0, 0)  # type: ignore[assignment]

if __version_info__ < (20, 0, 0, "alpha", 1):
    raise RuntimeError(
        f"This code is not compatible with your current PTB version {tg_ver}. It requires a version later than v20.0."
    )


def main() -> None:
    Logger.init_logger()

    Locale.init_locales()

    Database.init_db()

    Queries.register_fixed_queries()

    defaults = Defaults(parse_mode=ParseMode.HTML, tzinfo=pytz.timezone('Europe/Rome'), disable_web_page_preview=True)

    application = Application.builder().token(os_getenv("TOKEN")).defaults(defaults).build()
    application: Application

    application.job_queue.run_once(callback=SessionTable.expire_old_sessions, when=0)

    application.add_handler(MessageHandler(filters=filters.COMMAND, callback=Commands.commands_handler))
    application.add_handler(CallbackQueryHandler(callback=Queries.callback_queries_handler))

    GitHubMonitor.init(application.bot)

    application.job_queue.run_repeating(
        callback=GitHubMonitor.look_for_updates,
        interval=GitHubMonitor.interval,
        first=1
    )

    application.run_polling()


if __name__ == "__main__":
    main()

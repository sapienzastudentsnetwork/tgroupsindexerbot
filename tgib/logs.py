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

import logging

from telegram.ext import ContextTypes

from tgib.global_vars import GlobalVariables

import telegram.ext


class Logger:
    logger = None

    exception_log_chat_id = None

    @classmethod
    def init_logger(cls, exception_log_chat_id: int = None):
        logging.basicConfig(level=logging.INFO,
                            format='%(levelname)s - %(message)s')

        cls.logger = logging.getLogger()

        cls.exception_log_chat_id = exception_log_chat_id

    @classmethod
    def log(cls, log_type, author, text, exception=None) -> bool:
        message = f"{author} | {text}"

        if exception is not None:
            exception_type = str(type(exception)).replace("<class '", "").replace("'>", "")

            message += f"\n\n{exception_type}: {exception}"

        logger = cls.logger

        if log_type == "exception":
            logger.exception(message)

            bot_instance: telegram.Bot = GlobalVariables.bot_instance

            if cls.exception_log_chat_id:
                async def alert_on_telegram(context: ContextTypes.DEFAULT_TYPE) -> None:
                    print("exception_log_chat_id: " + str(cls.exception_log_chat_id))

                    try:
                        message_text = f"<b>EXCEPTION</b>\n\n<code>{author}</code>\n\n{text}"

                        if exception is not None:
                            message_text += f"\n\n<i><b>{exception_type}:</b> {exception}</i>"

                        await bot_instance.send_message(
                            chat_id=cls.exception_log_chat_id,
                            text=message_text
                        )

                    except Exception as ex:
                        ex_type = str(type(ex)).replace("<class '", "").replace("'>", "")

                        logger.exception(f"Logger.log.alert_on_telegram | {ex_type}: {ex}")

                GlobalVariables.job_queue.run_once(alert_on_telegram, when=0)

        elif log_type == "info":
            logger.info(message)
        elif log_type == "debug":
            logger.debug(message)
        elif log_type == "warning":
            logger.warning(message)
        elif log_type == "error":
            logger.error(message)
        elif log_type == "critical":
            logger.critical(message)
        else:
            return False

        return True

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


class Logger:
    logger = None

    @classmethod
    def init_logger(cls):
        logging.basicConfig(level=logging.INFO,
                            format='%(levelname)s - %(message)s')

        cls.logger = logging.getLogger()

    @classmethod
    def log(cls, log_type, author, text) -> bool:
        message = f"{author} | {text}"
        logger  = cls.logger

        if log_type == "exception":
            logger.exception(message)
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

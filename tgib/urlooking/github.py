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

import re
from os import getenv as os_getenv

import feedparser
import telegram.ext
from telegram.ext import ContextTypes

from tgib.data.database import PersistentVarsTable
from tgib.logs import Logger


class GitHubMonitor:
    tgib_bot_instance: telegram.Bot = None

    previous_atom_feed_update_date_key_name = "tgib_repo_atom_feed_latest_update_date"

    atom_feed_update_date = None

    tgib_repo_url = "https://github.com/sapienzastudentsnetwork/tgroupsindexerbot"

    tgib_repo_atom_feed_url = "https://github.com/sapienzastudentsnetwork/tgroupsindexerbot/commits.atom"

    tgib_telegram_git_channel_chat_id = "@TGroupsIndexerBotGit"

    interval = 150

    @classmethod
    def get_atom_feed(cls, atom_feed_url: str) -> feedparser.FeedParserDict:
        return feedparser.parse(atom_feed_url)

    @classmethod
    async def notify_update(cls, id: str, author: str, update_date: str, summary: str):
        await cls.tgib_bot_instance.send_message(
            chat_id=cls.tgib_telegram_git_channel_chat_id,
            text=f"<b><u>New Commit</u></b> <a href='{cls.tgib_repo_url}/commit/{id}'>[🌐]</a>"
                 f"\n\n👤 {author} • <code>{update_date}</code>"
                 f"\n\n{summary}"
        )

    @classmethod
    async def notify_updates_since(cls, update_date: str, atom_feed: feedparser.FeedParserDict):
        if "entries" in atom_feed:
            entries = atom_feed["entries"]
            update_entries = []

            for entry_dict in entries:
                if entry_dict["updated"] <= update_date:
                    break

                update_entries.append(entry_dict)

            for entry_dict in reversed(update_entries):
                entry_update_date = entry_dict["updated"]

                id = entry_dict["id"].split("/")[1]

                author_details = entry_dict["author_detail"]
                author = "<a href='" + author_details["href"] + "'>" + author_details["name"] + "</a>"

                summary = re.sub("<pre[^>]*>|</pre>", "", entry_dict["summary"])

                await cls.notify_update(id=id, author=author, update_date=entry_update_date, summary=summary)

    @classmethod
    def get_atom_feed_latest_update_date(cls, atom_feed: feedparser.FeedParserDict) -> (str | None):
        if "feed" in atom_feed:
            if "updated" in atom_feed["feed"]:
                return str(atom_feed["feed"]["updated"])

        return None

    @classmethod
    async def look_for_updates(cls, context: ContextTypes.DEFAULT_TYPE) -> None:
        Logger.log("info", "GitHubMonitor", "Checking the GitHub repository for updates")

        try:
            atom_feed = cls.get_atom_feed(cls.tgib_repo_atom_feed_url)

            current_atom_feed_update_date = cls.get_atom_feed_latest_update_date(atom_feed)

            previous_atom_feed_update_date = cls.atom_feed_update_date

            if current_atom_feed_update_date and current_atom_feed_update_date != previous_atom_feed_update_date:
                await cls.notify_updates_since(previous_atom_feed_update_date, atom_feed)

                PersistentVarsTable.update_value_by_key(
                    cls.previous_atom_feed_update_date_key_name,
                    current_atom_feed_update_date
                )

                cls.atom_feed_update_date = current_atom_feed_update_date

        except Exception as ex:
            Logger.log("exception", "GitHubMonitor",
                       f"An exception occurred while looking for updates", ex)

    @classmethod
    def init(cls, bot_instance: telegram.Bot):
        cls.tgib_bot_instance = bot_instance

        previous_atom_feed_update_date = PersistentVarsTable.get_value_by_key(
            cls.previous_atom_feed_update_date_key_name
        )

        if previous_atom_feed_update_date is None:
            atom_feed = cls.get_atom_feed(cls.tgib_repo_atom_feed_url)

            previous_atom_feed_update_date = cls.get_atom_feed_latest_update_date(atom_feed)

            cls.atom_feed_update_date = previous_atom_feed_update_date

            PersistentVarsTable.add_new_var(cls.previous_atom_feed_update_date_key_name, previous_atom_feed_update_date)
        else:
            cls.atom_feed_update_date = previous_atom_feed_update_date

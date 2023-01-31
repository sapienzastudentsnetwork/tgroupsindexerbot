import re
from os import getenv as os_getenv

import feedparser
import telegram.ext
from telegram.ext import ContextTypes

from ssb.data.database import PersistentVarsTable
from ssb.logs import Logger


class GitHubMonitor:
    ssb_bot_instance: telegram.Bot = None

    previous_atom_feed_update_date_key_name = "ssb_repo_atom_feed_latest_update_date"

    atom_feed_update_date = None

    ssb_repo_url = "https://github.com/sapienzastudentsnetwork/tgroupsindexerbot"

    ssb_repo_atom_feed_url = "https://github.com/sapienzastudentsnetwork/tgroupsindexerbot/commits.atom"

    ssb_telegram_git_channel_chat_id = "@TGroupsIndexerBotGit"

    interval = 150

    @classmethod
    def get_atom_feed(cls, atom_feed_url: str) -> feedparser.FeedParserDict:
        return feedparser.parse(atom_feed_url)

    @classmethod
    async def notify_update(cls, id: str, author: str, update_date: str, summary: str):
        await cls.ssb_bot_instance.send_message(
            chat_id=cls.ssb_telegram_git_channel_chat_id,
            text=f"<b><u>New Commit</u></b> <a href='{cls.ssb_repo_url}/commit/{id}'>[🌐]</a>"
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
    def get_atom_feed_latest_update_date(cls, atom_feed: feedparser.FeedParserDict):
        if "feed" in atom_feed:
            if "updated" in atom_feed["feed"]:
                return str(atom_feed["feed"]["updated"])

        return None

    @classmethod
    async def look_for_updates(cls, context: ContextTypes.DEFAULT_TYPE) -> None:
        Logger.log("info", "GitHubMonitor", "Checking the GitHub repository for updates")

        try:
            atom_feed = cls.get_atom_feed(cls.ssb_repo_atom_feed_url)

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
            Logger.log("exception", "GitHubMonitor", str(ex))

            try:
                await cls.ssb_bot_instance.send_message(
                    chat_id=os_getenv("DEVELOPER_CHAT_ID"),
                    text=f"<b>EXCEPTION</b>\n\n{ex}"
                )

            except:
                pass

    @classmethod
    def init(cls, bot_instance: telegram.Bot):
        cls.ssb_bot_instance = bot_instance

        previous_atom_feed_update_date = PersistentVarsTable.get_value_by_key(
            cls.previous_atom_feed_update_date_key_name
        )

        if previous_atom_feed_update_date is None:
            atom_feed = cls.get_atom_feed(cls.ssb_repo_atom_feed_url)

            previous_atom_feed_update_date = cls.get_atom_feed_latest_update_date(atom_feed)

            cls.atom_feed_update_date = previous_atom_feed_update_date

            PersistentVarsTable.add_new_var(cls.previous_atom_feed_update_date_key_name, previous_atom_feed_update_date)
        else:
            cls.atom_feed_update_date = previous_atom_feed_update_date

from os import getenv as os_getenv

import feedparser
import telegram.ext
from telegram.ext import ContextTypes

from ssb.data.database import PersistentVarsTable
from ssb.logs import Logger


class GitHubMonitor:
    ssb_bot_instance: telegram.Bot = None

    previous_atom_feed_update_date_key_name = "ssb_repo_atom_feed_latest_update_date"

    previous_atom_feed_update_date = None

    ssb_repo_url = "https://github.com/sapienzastudentsnetwork/sapienzastudentsbot"

    ssb_repo_atom_feed_url = "https://github.com/sapienzastudentsnetwork/sapienzastudentsbot/commits.atom"

    ssb_telegram_git_channel_chat_id = "@SapienzaStudentsBotGit"

    interval = 150

    @classmethod
    def get_atom_feed_latest_update_date(cls, atom_feed_url: str):
        feed = feedparser.parse(atom_feed_url)

        feed.pop("entries")

        if "feed" in feed:
            if "updated" in feed["feed"]:
                return str(feed["feed"]["updated"])

        return None

    async def look_for_updates(cls, context: ContextTypes.DEFAULT_TYPE) -> None:
        Logger.log("info", "GitHubMonitor", "Checking the GitHub repository for updates")

        try:
            current_atom_feed_update_date = cls.get_atom_feed_latest_update_date(cls.ssb_repo_atom_feed_url)

            if current_atom_feed_update_date and current_atom_feed_update_date != cls.previous_atom_feed_update_date:
                cls.previous_atom_feed_update_date = current_atom_feed_update_date

                PersistentVarsTable.update_value_by_key(
                    cls.previous_atom_feed_update_date_key_name,
                    current_atom_feed_update_date
                )

                await cls.ssb_bot_instance.send_message(
                    chat_id=cls.ssb_telegram_git_channel_chat_id,
                    text=f"A <b>new update</b> "
                         f"to the <a href='{cls.ssb_repo_url}'>GitHub repository</a> "
                         f"has been detected\n\n"
                         f"<b>Update date:</b> <code>{current_atom_feed_update_date}</code>"
                )

        except Exception as ex:
            Logger.log("exception", "GitHubMonitor", str(ex))

            try:
                await cls.ssb_bot_instance.send_message(
                    chat_id=os_getenv("MATYPIST_CHAT_ID"),
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
            previous_atom_feed_update_date = cls.get_atom_feed_latest_update_date(cls.ssb_repo_atom_feed_url)

            cls.previous_atom_feed_update_date = previous_atom_feed_update_date

            PersistentVarsTable.add_new_var(cls.previous_atom_feed_update_date_key_name, previous_atom_feed_update_date)
        else:
            cls.previous_atom_feed_update_date = previous_atom_feed_update_date

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

import time
from os import getenv as os_getenv
from urllib.parse import urlparse as urllib_parse_urlparse

import psycopg2
import telegram
from telegram.ext import ContextTypes

from tgib.global_vars import GlobalVariables
from tgib.ui.menus import Menus
from tgib.logs import Logger


class Database:
    connection = None
    POSTGRE_URI = os_getenv("DATABASE_URL")

    @classmethod
    def init_db(cls):
        try:
            result = urllib_parse_urlparse(cls.POSTGRE_URI)

            connection = psycopg2.connect(
                database=result.path[1:],
                user=result.username,
                password=result.password,
                host=result.hostname,
                port=result.port
            )

            cls.connection = connection

            cls.create_tables()

            return connection

        except (Exception, psycopg2.DatabaseError) as ex:
            Logger.log("exception", "Database.init_db",
                       f"An exception occurred while trying to connect to database: "
                       f"\n{ex}\n\nSHUTTING DOWN THE BOT...")

            exit()

        return None

    @classmethod
    def get_cursor(cls) -> (psycopg2._psycopg.cursor, bool):
        try:
            cursor = cls.connection.cursor()

            return cursor, True

        except psycopg2.InterfaceError as ie:
            Logger.log("warning", "Database.get_cursor",
                       f"An 'InterfaceError' exception occurred while trying to get connection cursor: \n{ie}"
                       f"\n\nTrying to recover by re-initializing the database")

            try:
                return cls.init_db().cursor(), True

            except (Exception, psycopg2.DatabaseError) as ex:
                Logger.log("critical", "Database.get_cursor",
                           f"An exception occurred while trying to init DB again to get connection cursor: \n{ex}")

                return None, False

        except (Exception, psycopg2.DatabaseError) as ex:
            Logger.log("exception", "Database.get_cursor",
                       f"An exception occurred while trying to get connection cursor: \n{ex}")

            return None, False

    @classmethod
    def create_tables(cls) -> None:
        cursor, iscursor = Database.get_cursor()

        return_value = 0

        if iscursor:
            cursor: psycopg2._psycopg.cursor

            connection = Database.connection
            connection: psycopg2._psycopg.connection

            try:
                # directory
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS directory (
                        id SERIAL PRIMARY KEY,
                        i18n_it_name VARCHAR(255) NOT NULL,
                        i18n_en_name VARCHAR(255),
                        parent_id INT,
                        FOREIGN KEY (parent_id) REFERENCES directory(id)
                    );
                    """
                )

                # chat
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS chat (
                        chat_id BIGINT PRIMARY KEY,
                        title VARCHAR(128),
                        invite_link VARCHAR(38),
                        custom_link VARCHAR(60),
                        chat_admins BIGINT[],
                        directory_id INT,
                        hidden_by BIGINT,
                        created_at TIMESTAMP DEFAULT now(),
                        updated_at TIMESTAMP DEFAULT now(),
                        FOREIGN KEY (directory_id) REFERENCES directory(id),
                        FOREIGN KEY (hidden_by) REFERENCES account(chat_id)
                    );
                    """
                )

                # account
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS account (
                        chat_id BIGINT PRIMARY KEY,
                        created_at TIMESTAMP DEFAULT now(),
                        pref_lang_code VARCHAR(4),
                        is_admin BOOLEAN DEFAULT false,
                        can_view_groups BOOLEAN DEFAULT true,
                        can_add_groups BOOLEAN DEFAULT true,
                        can_modify_groups BOOLEAN DEFAULT true
                    );
                    """
                )

                # session
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS session (
                        chat_id BIGINT PRIMARY KEY,
                        created_at TIMESTAMP DEFAULT now(),
                        menu_message_id BIGINT
                    );
                    """
                )

                # persistent_vars
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS persistent_vars (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL DEFAULT '',
                        created_at TIMESTAMP DEFAULT now(),
                        updated_at TIMESTAMP DEFAULT now()
                    );
                    """
                )

                connection.commit()
            except (Exception, psycopg2.DatabaseError) as ex:
                Logger.log("exception", "Database.create_tables",
                           f"An exception occurred while trying to create a table: \n{ex}")

        else:
            Logger.log("error", "Database.create_tables", f"Couldn't get cursor required to create tables")


class AccountTable:
    cached_account_records = {}

    @classmethod
    def get_account_records_count(cls) -> int:
        cursor, iscursor = Database.get_cursor()

        if iscursor:
            cursor: psycopg2._psycopg.cursor

            try:
                cursor.execute("SELECT COUNT(*) FROM account")

                return cursor.fetchone()[0]

            except (Exception, psycopg2.DatabaseError) as ex:
                Logger.log("exception", "AccountTable.get_account_records_count",
                           f"An exception occurred while trying to get the number of account records: \n{ex}")

                return -1

        else:
            Logger.log("error", "AccountTable.get_account_records_count",
                       f"Couldn't get cursor required to get the number of groups")

            return -1

    @classmethod
    def create_account_record(cls, chat_id: int) -> bool:
        cursor, iscursor = Database.get_cursor()

        if iscursor:
            try:
                cursor.execute(
                    "INSERT INTO account (chat_id, created_at) "
                    "VALUES (%s, now() AT TIME ZONE 'Europe/Rome')",
                    (chat_id,)
                )

                GlobalVariables.increment_accounts_count()

                return True

            except (Exception, psycopg2.DatabaseError) as ex:
                Logger.log("exception", "Database.create_user_record",
                           f"An exception occurred while trying to create account record for '{chat_id}': \n{ex}")

                return False

        else:
            Logger.log("error", "Database.create_user_record", f"Couldn't get cursor required to create account record")

            return False

    @classmethod
    def get_account_record(cls, chat_id: int) -> (dict, bool):
        if chat_id not in cls.cached_account_records:
            cursor, iscursor = Database.get_cursor()

            if iscursor:
                cursor: psycopg2._psycopg.cursor

                try:
                    cursor.execute("SELECT * FROM account WHERE chat_id = %s", (chat_id,))

                    account_record = cursor.fetchone()

                    if account_record is not None:
                        columns = [desc[0] for desc in cursor.description]
                        user_data = dict(zip(columns, account_record))

                        cls.cached_account_records[chat_id] = user_data

                        return user_data, True
                    else:
                        if AccountTable.create_account_record(chat_id):
                            return AccountTable.get_account_record(chat_id)
                        else:
                            return {}, False

                except (Exception, psycopg2.DatabaseError) as ex:
                    Logger.log("exception", "Database.get_user",
                               f"An exception occurred while trying to get account record with '{chat_id}' as chat_id: \n{ex}")

                    return {}, False

            else:
                Logger.log("error", "Database.get_user", f"Couldn't get cursor required to get user")

                return {}, False
        else:
            return cls.cached_account_records[chat_id], True


class DirectoryTable:
    CATEGORIES_ROOT_DIR_ID = 1

    cached_directory_records = {}

    cached_sub_directories = {}

    @classmethod
    def get_directory_data(cls, directory_id: int):
        if directory_id not in cls.cached_directory_records:
            cursor, iscursor = Database.get_cursor()

            if iscursor:
                cursor: psycopg2._psycopg.cursor

                try:
                    cursor.execute("SELECT * FROM directory WHERE id = %s", (directory_id,))

                    directory_record = cursor.fetchone()

                    if directory_record is not None:
                        columns = [desc[0] for desc in cursor.description]

                        directory_data = dict(zip(columns, directory_record))

                        cls.cached_directory_records[directory_id] = directory_data

                        return directory_data, True
                    else:
                        return {}, False

                except (Exception, psycopg2.DatabaseError) as ex:
                    Logger.log("exception", "Database.get_directory_data",
                               f"An exception occurred while trying to get directory name for directory "
                               f"having id equal to '{directory_id}': \n{ex}")

                    return {}, False

            else:
                Logger.log("error", "Database.get_directory_data", f"Couldn't get cursor required to get directory name")

                return {}, False
        else:
            return cls.cached_directory_records[directory_id], True

    @classmethod
    def get_sub_directories(cls, parent_id: int) -> (dir, bool):
        if parent_id not in cls.cached_sub_directories:
            cursor, iscursor = Database.get_cursor()

            if iscursor:
                cursor: psycopg2._psycopg.cursor

                try:
                    cursor.execute("SELECT * FROM directory "
                                   "WHERE parent_id = %s AND (i18n_it_name != '' OR i18n_en_name != '')", (parent_id,))

                    directories_records = cursor.fetchall()

                    if directories_records is not None:
                        columns = [desc[0] for desc in cursor.description if desc[0] != "id"]

                        sub_directories = {directory_record[0]: dict(zip(columns, directory_record[1:])) for directory_record in directories_records}

                        cls.cached_sub_directories[parent_id] = sub_directories

                        return sub_directories, True
                    else:
                        return {}, True

                except (Exception, psycopg2.DatabaseError) as ex:
                    Logger.log("exception", "Database.get_sub_directories",
                               f"An exception occurred while trying to get sub-directories of "
                               f"directory with parent_id equal to '{parent_id}': \n{ex}")

                    return {}, False

            else:
                Logger.log("error", "Database.get_sub_directories", f"Couldn't get cursor required to get sub-directories")

                return {}, False
        else:
            return cls.cached_sub_directories[parent_id], True


class ChatTable:
    cached_chat_counts = {}

    @classmethod
    def get_chat_count(cls, directory_id: int) -> (int, bool):
        if directory_id not in cls.cached_chat_counts:
            cursor, iscursor = Database.get_cursor()

            if iscursor:
                cursor: psycopg2._psycopg.cursor

                try:
                    cursor.execute(
                        """
                        WITH RECURSIVE subdirectories AS (
                            SELECT id FROM directory WHERE id = %s
                            UNION
                            SELECT directory.id FROM directory
                            JOIN subdirectories ON directory.parent_id = subdirectories.id
                        )
                        SELECT id, COUNT(chat.chat_id) as total_chats
                        FROM subdirectories
                        LEFT JOIN chat ON subdirectories.id = chat.directory_id
                        GROUP BY subdirectories.id;
                        """, (directory_id,)
                    )

                    result = cursor.fetchall()

                    chats_count = 0

                    for sub_directory_id, sub_directory_chats_count in result:
                        chats_count += sub_directory_chats_count

                    cls.cached_chat_counts[directory_id] = chats_count

                    return chats_count, True

                except (Exception, psycopg2.DatabaseError) as ex:
                    Logger.log("exception", "Database.get_chat_count",
                               f"An exception occurred while trying to get the number of chats "
                               f"with a parent directory having id '{directory_id}': \n{ex}")

                    return -1, False

            else:
                Logger.log("error", "Database.get_chat_count",
                           f"Couldn't get cursor required to get the number of chats "
                           f"with a parent directory having id '{directory_id}'")

                return -1, False
        else:
            return cls.cached_chat_counts[directory_id], True

    @classmethod
    def chat_records_to_dict(cls, column_names: list, records: list) -> dict:
        chats = {}

        for record in records:
            chat_id = record[0]

            chat_data = {}
            for i, column_name in enumerate(column_names):
                if i == 0:
                    continue
                chat_data[column_name] = record[i]

            chats[chat_id] = chat_data

        return chats

    @classmethod
    def get_chats(cls, directory_id: int, skip_hidden_chats: bool = True) -> (dict, bool):
        cursor, iscursor = Database.get_cursor()

        if iscursor:
            cursor: psycopg2._psycopg.cursor

            where_string = "WHERE directory_id = %s"

            if skip_hidden_chats:
                where_string += " AND hidden_by IS NULL"

            cursor.execute("SELECT * FROM chat "
                           f"{where_string} "
                           "ORDER BY title ASC", (directory_id,))

            column_names = [desc[0] for desc in cursor.description]
            records = cursor.fetchall()

            chats = cls.chat_records_to_dict(column_names, records)

            return chats, True

        else:
            Logger.log("error", "Database.get_chats", f"Couldn't get cursor required to get chats")

            return {}, False

    @classmethod
    async def fetch_chats(cls, context: ContextTypes.DEFAULT_TYPE) -> None:
        bot_instance = context.job.data
        bot_instance: telegram.Bot

        cursor, iscursor = Database.get_cursor()

        if iscursor:
            cursor: psycopg2._psycopg.cursor

            cursor.execute("SELECT * FROM chat")

            column_names = [desc[0] for desc in cursor.description]
            records = cursor.fetchall()

            chats = cls.chat_records_to_dict(column_names, records)

            for chat_id, chat_data in chats.items():
                saved_title = chat_data["title"]

                saved_invite_link = chat_data["invite_link"]

                try:
                    chat = await bot_instance.getChat(chat_id)

                except telegram.error.RetryAfter as ex:
                    Logger.log("exception", "Database.fetch_chats", str(ex))

                    time.sleep(ex.retry_after)

                    chat = await bot_instance.getChat(chat_id)

                chat: telegram.Chat

                current_title = chat.title

                current_invite_link = chat.invite_link

                #

                saved_chat_admins = chat_data["chat_admins"]

                current_chat_admins = []

                try:
                    chat_admins = await bot_instance.get_chat_administrators(chat_id)

                except telegram.error.RetryAfter as ex:
                    Logger.log("exception", "Database.fetch_chats", str(ex))

                    time.sleep(ex.retry_after)

                    chat_admins = await bot_instance.get_chat_administrators(chat_id)

                for admin in chat_admins:
                    admin: telegram.ChatMember

                    current_chat_admins.append(admin.user.id)

                #

                if [current_chat_admins] != saved_chat_admins or current_title != saved_title or current_invite_link != saved_invite_link:
                    query = """
                        UPDATE chat
                        SET 
                            title = %s,
                            invite_link = %s,
                            chat_admins = %s
                        WHERE chat_id = %s;
                    """

                    saved_values = (saved_title, saved_invite_link, saved_chat_admins, chat_id)

                    Logger.log("debug", "Database.fetch_chats", f"Old (saved) values: {saved_values}")

                    query_vars = (current_title, current_invite_link, current_chat_admins, chat_id)

                    Logger.log("debug", "Database.fetch_chats", f"New (current) values: {query_vars}")

                    try:
                        cursor.execute(query, query_vars)

                        Database.connection.commit()

                        Logger.log("debug", "Database.fetch_chats", f"Succesfully updated chat '{chat_id}' info")

                    except (Exception, psycopg2.DatabaseError) as ex:
                        Logger.log("exception", "Database.fetch_chats", f"Couldn't update chat '{chat_id}': \n{ex}")

                time.sleep(1)

        else:
            Logger.log("error", "Database.fetch_chats", f"Couldn't get cursor required to fetch chats")


class SessionTable:
    active_chat_sessions = {}

    @classmethod
    def get_active_session_menu_message_id(cls, chat_id: int) -> int:
        if chat_id in cls.active_chat_sessions:
            return cls.active_chat_sessions[chat_id]
        else:
            return -1

    @classmethod
    def add_session(cls, chat_id: int, latest_menu_message_id: int) -> None:
        cls.active_chat_sessions[chat_id] = latest_menu_message_id

        cursor, iscursor = Database.get_cursor()

        if iscursor:
            cursor: psycopg2._psycopg.cursor

            try:
                connection = Database.connection
                connection: psycopg2._psycopg.connection

                cursor.execute("INSERT INTO session (chat_id, menu_message_id) VALUES (%s, %s)",
                               (chat_id, latest_menu_message_id))
                connection.commit()

            except (Exception, psycopg2.DatabaseError) as ex:
                Logger.log("critical", "Database.add_session",
                           f"An exception occurred while trying to insert '{latest_menu_message_id}' "
                           f"latest_menu_message_id in 'session' table for '{chat_id}': \n{ex}")

        else:
            Logger.log("error", "Database.add_session", f"Couldn't get cursor required to insert session data")

    @classmethod
    def update_session(cls, chat_id: int, new_latest_menu_message_id: int) -> None:
        cls.active_chat_sessions[chat_id] = new_latest_menu_message_id

        cursor, iscursor = Database.get_cursor()

        if iscursor:
            cursor: psycopg2._psycopg.cursor

            try:
                connection = Database.connection
                connection: psycopg2._psycopg.connection

                cursor.execute("UPDATE session SET menu_message_id = %s WHERE chat_id = %s",
                               (new_latest_menu_message_id, chat_id))

                connection.commit()

            except (Exception, psycopg2.DatabaseError) as ex:
                Logger.log("critical", "Database.update_session",
                           f"An exception occurred while trying to update latest_menu_message_id for "
                           f"'{chat_id}' to `{new_latest_menu_message_id}': \n{ex}")

        else:
            Logger.log("error", "Database.update_session", f"Couldn't get cursor required to update session data")

    @classmethod
    async def expire_old_sessions(cls, context: ContextTypes.DEFAULT_TYPE) -> None:
        cursor, iscursor = Database.get_cursor()

        if iscursor:
            cursor: psycopg2._psycopg.cursor

            try:
                connection = Database.connection
                connection: psycopg2._psycopg.connection

                cursor.execute("SELECT chat_id, menu_message_id FROM session")

                records = cursor.fetchall()

                for record in records:
                    chat_id, menu_message_id = record

                    text, reply_markup = Menus.get_expired_session_menu()

                    from tgib.handlers.queries import Queries
                    reply_markup = Queries.encode_queries(reply_markup)

                    try:
                        await context.bot.edit_message_text(chat_id=chat_id, message_id=menu_message_id,
                                                            text=text, reply_markup=reply_markup)
                    except Exception:
                        pass

                cursor.execute("DELETE FROM session")

                connection.commit()

            except (Exception, psycopg2.DatabaseError) as ex:
                Logger.log("critical", "Database.expire_old_sessions",
                           f"An exception occurred while trying to expire old sessions: \n{ex}")

        else:
            Logger.log("error", "Database.expire_old_sessions", f"Couldn't get cursor required to expire old sessions")


class PersistentVarsTable:
    @classmethod
    def add_new_var(cls, key: str, value: str):
        cursor, iscursor = Database.get_cursor()

        updated = False

        if iscursor:
            cursor: psycopg2._psycopg.cursor

            connection = Database.connection
            connection: psycopg2._psycopg.connection

            try:
                cursor.execute(
                    "INSERT INTO persistent_vars (key, value, created_at, updated_at) "
                    "VALUES (%s, %s, NOW() AT TIME ZONE 'Europe/Rome', NOW() AT TIME ZONE 'Europe/Rome')",
                    (key, value)
                )

                connection.commit()

            except (Exception, psycopg2.DatabaseError) as ex:
                Logger.log("critical", "PersistentVarsTable.add_new_var",
                           f"An exception occurred while trying to add '{key}' with value '{value}': \n{ex}")
        else:
            Logger.log("error", "PersistentVarsTable.add_new_var",
                       f"Couldn't get cursor required to add '{key}' with value '{value}'")

        return updated

    @classmethod
    def update_value_by_key(cls, key: str, new_value: str):
        cursor, iscursor = Database.get_cursor()

        updated = False

        if iscursor:
            cursor: psycopg2._psycopg.cursor

            connection = Database.connection
            connection: psycopg2._psycopg.connection

            try:
                cursor.execute(
                    "UPDATE persistent_vars "
                    "SET value = %s, updated_at = now() AT TIME ZONE 'Europe/Rome' "
                    "WHERE key = %s", (new_value, key)
                )

                connection.commit()

            except (Exception, psycopg2.DatabaseError) as ex:
                Logger.log("critical", "PersistentVarsTable.update_value_by_key",
                           f"An exception occurred while trying to update '{key}' value to '{new_value}': \n{ex}")
        else:
            Logger.log("error", "PersistentVarsTable.update_value_by_key",
                       f"Couldn't get cursor required to update '{key}' value to '{new_value}'")

        return updated

    @classmethod
    def get_value_by_key(cls, key: str) -> (str | None):
        cursor, iscursor = Database.get_cursor()

        if iscursor:
            try:
                cursor.execute("SELECT value FROM persistent_vars WHERE key = %s", (key,))

                result = cursor.fetchone()

                if result:
                    return result[0]

            except (Exception, psycopg2.DatabaseError) as ex:
                Logger.log("critical", "PersistentVarsTable.get_value_by_key",
                           f"An exception occurred while trying to get '{key}' value: \n{ex}")
        else:
            Logger.log("error", "PersistentVarsTable.get_value_by_key",
                       f"Couldn't get cursor required to get '{key}' value")

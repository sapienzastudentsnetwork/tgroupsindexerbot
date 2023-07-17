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

import random
import time
from os import getenv as os_getenv
from urllib.parse import urlparse as urllib_parse_urlparse

import psycopg2
import telegram
from telegram import ChatMemberAdministrator
from telegram.ext import ContextTypes

from tgib.global_vars import GlobalVariables
from tgib.i18n.locales import Locale
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

    @classmethod
    def get_cursor(cls) -> (psycopg2._psycopg.cursor | None, bool):
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
                           f"An exception occurred while trying to init DB again to get connection cursor", ex)

                return None, False

        except (Exception, psycopg2.DatabaseError) as ex:
            Logger.log("exception", "Database.get_cursor",
                       f"An exception occurred while trying to get connection cursor", ex)

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
                        i18n_en_name VARCHAR(255),
                        i18n_it_name VARCHAR(255),
                        parent_id INT,
                        FOREIGN KEY (parent_id) REFERENCES directory(id)
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
                        missing_permissions BOOLEAN DEFAULT TRUE,
                        FOREIGN KEY (directory_id) REFERENCES directory(id),
                        FOREIGN KEY (hidden_by) REFERENCES account(chat_id)
                    );
                    """
                )

                # Check if the 'missing_permissions' column in 'chat' table already exists
                cursor.execute("""
                    SELECT EXISTS (
                        SELECT 1
                        FROM information_schema.columns
                        WHERE table_name = 'chat' AND column_name = 'missing_permissions'
                    )
                """)
                column_exists = cursor.fetchone()[0]

                # Add the 'missing_permissions' column to 'chat' table if it doesn't exist
                if not column_exists:
                    cursor.execute("""
                        ALTER TABLE chat
                        ADD COLUMN missing_permissions BOOLEAN DEFAULT TRUE
                    """)

                # Check if the "update_timestamp" trigger function already exists
                cursor.execute("""
                    SELECT 1
                    FROM pg_trigger
                    WHERE tgname = 'update_chat_timestamp'
                """)
                trigger_exists = cursor.fetchone()

                # Create "update_timestamp" trigger function if it doesn't exist
                if not trigger_exists:
                    cursor.execute("""
                        CREATE OR REPLACE FUNCTION update_timestamp()
                        RETURNS TRIGGER AS $$
                        BEGIN
                            NEW.updated_at = NOW();
                            RETURN NEW;
                        END;
                        $$ LANGUAGE plpgsql;
                    """)

                # Check if "update_chat_timestamp" trigger exists
                cursor.execute("""
                    SELECT 1
                    FROM pg_trigger
                    WHERE tgname = 'update_chat_timestamp'
                """)
                trigger_exists = cursor.fetchone()

                # Create "update_chat_timestamp" trigger if it doesn't exist
                if not trigger_exists:
                    cursor.execute("""
                        CREATE TRIGGER update_chat_timestamp
                        BEFORE UPDATE ON chat
                        FOR EACH ROW
                        EXECUTE FUNCTION update_timestamp();
                    """)

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
                           f"An exception occurred while trying to create a table", ex)

        else:
            Logger.log("error", "Database.create_tables", f"Couldn't get cursor required to create tables")

    @classmethod
    def record_to_dict(cls, column_names: list, record: list) -> (dict | None):
        if record:
            record_dict = {}
            for i, column_name in enumerate(column_names):
                record_dict[column_name] = record[i]

            return record_dict
        else:
            return None

    @classmethod
    def records_to_dict(cls, column_names: list, records: list) -> dict:
        records_dict = {}

        if records:
            for record in records:
                primary_key_value = record[0]

                record_dict = cls.record_to_dict(column_names, record)

                records_dict[primary_key_value] = record_dict

        return records_dict


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
                           f"An exception occurred while trying to get the number of account records", ex)

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
                Logger.log("exception", "AccountTable.create_account_record",
                           f"An exception occurred while trying to create account record for '{chat_id}'", ex)

                return False

        else:
            Logger.log("error", "AccountTable.create_account_record",
                       f"Couldn't get cursor required to create account record")

            return False

    @classmethod
    def update_admin_status(cls, chat_id: int, new_value: bool) -> bool:
        cursor, iscursor = Database.get_cursor()

        if iscursor:
            try:
                connection = Database.connection
                connection: psycopg2._psycopg.connection

                cursor.execute(
                    """
                    UPDATE account
                    SET is_admin = %s
                    WHERE chat_id = %s;
                    """,
                    (new_value, chat_id)
                )

                connection.commit()

                if chat_id in cls.cached_account_records:
                    cls.cached_account_records[chat_id]["is_admin"] = new_value

                return True

            except (Exception, psycopg2.DatabaseError) as ex:
                Logger.log("exception", "ChatTable.change_admin_status",
                           f"Couldn't update admin status to '{new_value}' for user having chat_id '{chat_id}'", ex)

                return False

        else:
            Logger.log("error", "ChatTable.change_admin_status", f"Couldn't get cursor required to update admin status"
                                                                 f" to '{new_value}' for user having id '{chat_id}'")

            return False

    @classmethod
    def get_bot_admin_records(cls) -> (dict | None, bool):
        cursor, iscursor = Database.get_cursor()

        if iscursor:
            cursor: psycopg2._psycopg.cursor

            try:
                cursor.execute("SELECT * FROM account WHERE is_admin IS TRUE")

                column_names = [desc[0] for desc in cursor.description]
                records = cursor.fetchall()

                return Database.records_to_dict(column_names, records), True

            except (Exception, psycopg2.DatabaseError) as ex:
                Logger.log("exception", "AccountTable.get_bot_admin_records",
                           f"An exception occurred while trying to get bot admin account records", ex)

                return None, False

        else:
            Logger.log("error", "AccountTable.get_bot_admin_records",
                       f"Couldn't get cursor required to get bot admin account records")

            return None, False

    @classmethod
    def get_account_record(cls, chat_id: int, create_if_not_existing: bool = True) -> (dict | None, bool):
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
                        if create_if_not_existing and AccountTable.create_account_record(chat_id):
                            return AccountTable.get_account_record(chat_id, False)
                        else:
                            return None, False

                except (Exception, psycopg2.DatabaseError) as ex:
                    Logger.log("exception", "AccountTable.get_account_record",
                               f"An exception occurred while trying to get account record with '{chat_id}' as chat_id", ex)

                    return None, False

            else:
                Logger.log("error", "AccountTable.get_account_record", f"Couldn't get cursor required to get user")

                return None, False
        else:
            return cls.cached_account_records[chat_id], True


class DirectoryTable:
    CATEGORIES_ROOT_DIR_ID = 1

    cached_directory_records = {}

    cached_sub_directories = {}

    cached_chat_counts = {}

    @classmethod
    def create_directory(cls, i18n_en_name: str, i18n_it_name: str = None, directory_id: int = None, parent_directory_id: int = None) -> (int | None, bool):
        cursor, iscursor = Database.get_cursor()

        if iscursor:
            cursor: psycopg2._psycopg.cursor

            try:
                cursor.execute(
                    """
                    INSERT INTO directory (i18n_en_name, i18n_it_name, id, parent_id)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id;
                    """,
                    (i18n_en_name, i18n_it_name, directory_id, parent_directory_id)
                )

                inserted_id = cursor.fetchone()[0]

                Database.connection.commit()

                Logger.log(
                    "debug",
                    "DirectoryTable.create_directory",
                    f"A new directory has been created"
                        f"\n-           ID: {inserted_id}"
                        f"\n-    Parent ID: {parent_directory_id}"
                        f"\n- i18n_en_name: \"{i18n_en_name}\""
                        f"\n- i18n_it_name: \"{i18n_it_name}\""
                )

                return inserted_id, True

            except (Exception, psycopg2.DatabaseError) as ex:
                Logger.log("exception", "DirectoryTable.create_directory",
                           f"An exception occurred while trying to create a new directory", ex)

                return None, False

        else:
            Logger.log("error", "DirectoryTable.create_directory",
                       f"Couldn't get cursor required to create a new directory")

            return None, False

    @classmethod
    def get_directory_data(cls, directory_id: int) -> (dict | None, bool):
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
                    Logger.log("exception", "DirectoryTable.get_directory_data",
                               f"An exception occurred while trying to get directory name for directory "
                               f"having id equal to '{directory_id}'", ex)

                    return None, False

            else:
                Logger.log("error", "DirectoryTable.get_directory_data",
                           f"Couldn't get cursor required to get directory name")

                return None, False
        else:
            return cls.cached_directory_records[directory_id], True

    @classmethod
    def get_sub_directories(cls, parent_id: int) -> (dict | None, bool):
        if parent_id not in cls.cached_sub_directories:
            cursor, iscursor = Database.get_cursor()

            if iscursor:
                cursor: psycopg2._psycopg.cursor

                try:
                    cursor.execute("SELECT * FROM directory WHERE parent_id = %s", (parent_id,))

                    directories_records = cursor.fetchall()

                    if directories_records is not None:
                        columns = [desc[0] for desc in cursor.description if desc[0] != "id"]

                        sub_directories = {directory_record[0]: dict(zip(columns, directory_record[1:])) for directory_record in directories_records}

                        cls.cached_sub_directories[parent_id] = sub_directories

                        return sub_directories, True
                    else:
                        return {}, True

                except (Exception, psycopg2.DatabaseError) as ex:
                    Logger.log("exception", "DirectoryTable.get_sub_directories",
                               f"An exception occurred while trying to get sub-directories of "
                               f"directory with parent_id equal to '{parent_id}'", ex)

                    return None, False

            else:
                Logger.log("error", "DirectoryTable.get_sub_directories",
                           f"Couldn't get cursor required to get sub-directories")

                return None, False
        else:
            return cls.cached_sub_directories[parent_id], True

    @classmethod
    def get_chats_count(cls, directory_id: int) -> (int, bool):
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
                            AND chat.hidden_by IS NULL
                            AND chat.missing_permissions = FALSE
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
                    Logger.log("exception", "DirectoryTable.get_chat_count",
                               f"An exception occurred while trying to get the number of chats "
                               f"with a parent directory having id '{directory_id}'", ex)

                    return -1, False

            else:
                Logger.log("error", "DirectoryTable.get_chat_count",
                           f"Couldn't get cursor required to get the number of chats "
                           f"with a parent directory having id '{directory_id}'")

                return -1, False
        else:
            return cls.cached_chat_counts[directory_id], True

    @classmethod
    def increment_chats_count(cls, directory_id: int, increment: int = 1) -> None:
        if not cls.cached_chat_counts:
            return

        curr_directory_id = directory_id

        curr_directory_data, is_curr_directory_data = cls.get_directory_data(directory_id)

        while True:
            if is_curr_directory_data and curr_directory_data["parent_id"] and curr_directory_id in cls.cached_chat_counts:
                cls.cached_chat_counts[curr_directory_id] = cls.cached_chat_counts[curr_directory_id] + increment

            if not is_curr_directory_data or curr_directory_data["parent_id"] is None:
                break

            curr_directory_id = curr_directory_data["parent_id"]
            curr_directory_data, is_curr_directory_data = cls.get_directory_data(curr_directory_id)

    @classmethod
    def get_full_category_name(cls, user_lang_code: str, directory_id: int, separator: str = " » ") -> str:
        def_lang_code = Locale.def_lang_code

        full_category_name = None

        curr_directory_data, is_curr_directory_data = cls.get_directory_data(directory_id)

        while True:
            if is_curr_directory_data and (curr_directory_data[f"i18n_{user_lang_code}_name"] or curr_directory_data[f"i18n_{def_lang_code}_name"]):
                if curr_directory_data[f"i18n_{user_lang_code}_name"]:
                    curr_directory_name = curr_directory_data[f"i18n_{user_lang_code}_name"]
                else:
                    curr_directory_name = curr_directory_data[f"i18n_{def_lang_code}_name"]

                if full_category_name is None:
                    full_category_name = curr_directory_name
                else:
                    full_category_name = curr_directory_name + separator + full_category_name

            if not is_curr_directory_data or curr_directory_data["parent_id"] is None:
                break

            curr_parent_directory_id = curr_directory_data["parent_id"]
            curr_directory_data, is_curr_directory_data = cls.get_directory_data(curr_parent_directory_id)

        return full_category_name


class ChatTable:
    @classmethod
    def get_chats(cls, directory_id: int, skip_missing_permissions_chats: bool = True, skip_hidden_chats: bool = True) -> (dict | None, bool):
        cursor, iscursor = Database.get_cursor()

        if iscursor:
            cursor: psycopg2._psycopg.cursor

            where_string = "WHERE directory_id = %s"

            if skip_missing_permissions_chats:
                where_string += " AND missing_permissions = FALSE"

            if skip_hidden_chats:
                where_string += " AND hidden_by IS NULL"

            cursor.execute("SELECT * FROM chat "
                           f"{where_string} "
                           "ORDER BY title ASC", (directory_id,))

            column_names = [desc[0] for desc in cursor.description]
            records = cursor.fetchall()

            chats = Database.records_to_dict(column_names, records)

            return chats, True

        else:
            Logger.log("error", "ChatTable.get_chats", f"Couldn't get cursor required to get chats")

            return None, False

    @classmethod
    def update_chat_visibility(cls, chat_id: int, hidden_by: int = None) -> bool:
        cursor, iscursor = Database.get_cursor()

        if iscursor:
            try:
                connection = Database.connection
                connection: psycopg2._psycopg.connection

                cursor.execute(
                    """
                    UPDATE chat
                    SET hidden_by = %s
                    WHERE chat_id = %s;
                    """,
                    (hidden_by, chat_id)
                )

                connection.commit()

                return True

            except (Exception, psycopg2.DatabaseError) as ex:
                Logger.log("exception", "ChatTable.update_chat_visibility",
                           f"Couldn't update visibility to hidden by '{hidden_by}' for chat having id '{chat_id}'", ex)

                return False

        else:
            Logger.log("error", "ChatTable.update_chat_visibility", f"Couldn't get cursor required to update visibility to"
                                                                    f" hidden by '{hidden_by}' for chat having id '{chat_id}'")

            return False

    @classmethod
    def update_chat_directory(cls, chat_id: int, new_directory_id: int) -> bool:
        cursor, iscursor = Database.get_cursor()

        if iscursor:
            try:
                connection = Database.connection
                connection: psycopg2._psycopg.connection

                cursor.execute(
                    """
                    UPDATE chat
                    SET directory_id = %s
                    WHERE chat_id = %s;
                    """,
                    (new_directory_id, chat_id)
                )

                connection.commit()

                return True

            except (Exception, psycopg2.DatabaseError) as ex:
                Logger.log("exception", "ChatTable.update_chat_directory",
                           f"Couldn't update directory_id to '{new_directory_id}' for chat having id '{chat_id}'", ex)

                return False

        else:
            Logger.log("error", "ChatTable.update_chat_directory", f"Couldn't get cursor required to update directory_id"
                                                                   f" to '{new_directory_id}' for chat having id '{chat_id}'")

            return False

    @classmethod
    def migrate_chat_id(cls, old_chat_id: int, new_chat_id: int) -> bool:
        cursor, iscursor = Database.get_cursor()

        if iscursor:
            old_chat_data, is_old_chat_data = ChatTable.get_chat_data(cursor, old_chat_id)

            if is_old_chat_data:
                try:
                    connection = Database.connection
                    connection: psycopg2._psycopg.connection

                    cursor.execute(
                        """
                        UPDATE chat
                        SET custom_link = %s,
                            directory_id = %s,
                            hidden_by = %s
                        WHERE chat_id = %s;
                        """,
                        (old_chat_data["custom_link"], old_chat_data["directory_id"], old_chat_data["hidden_by"], new_chat_id)
                    )

                    connection.commit()

                    removed = ChatTable.remove_chat(old_chat_id)

                    if removed:
                        Logger.log("info", "ChatTable.migrate_chat_id",
                                   f"Successfully updated data of supergroup having chat_id = '{new_chat_id}'"
                                   f" by migrating them from data associated to its previous chat_id ('{old_chat_id}')")

                except (Exception, psycopg2.DatabaseError) as ex:
                    Logger.log("exception", "ChatTable.migrate_chat_id",
                               f"Couldn't update data of supergroup having '{new_chat_id}'"
                               f" by migrating them from data associated to its previous chat_id '{old_chat_id}", ex)

                    return False

            return is_old_chat_data

        else:
            Logger.log("error", "ChatTable.migrate_chat_id", f"Couldn't get cursor required to update data of"
                                                             f" supergroup having '{new_chat_id}' by migrating"
                                                             f" them from data associated to its previous chat_id"
                                                             f" '{new_chat_id}'")

            return False

    @classmethod
    def set_missing_permissions(cls, chat_id: int) -> bool:
        cursor, iscursor = Database.get_cursor()

        if iscursor:
            # Check if missing_permissions is already TRUE
            try:
                cursor.execute("""
                    SELECT missing_permissions, directory_id
                    FROM chat
                    WHERE chat_id = %s
                """, (chat_id,))
                result = cursor.fetchone()

                # Update missing_permissions and decrement chats count if missing_permissions it's not already TRUE
                if result and not result[0]:
                    query = """
                        UPDATE chat
                        SET missing_permissions = TRUE
                        WHERE chat_id = %s
                    """

                    try:
                        connection = Database.connection
                        connection: psycopg2._psycopg.connection

                        cursor.execute(query, (chat_id,))

                        connection.commit()

                        directory_id = result[1]
                        if directory_id is not None:
                            DirectoryTable.increment_chats_count(directory_id, -1)

                        return True

                    except (Exception, psycopg2.DatabaseError) as ex:
                        Logger.log("exception", "ChatTable.set_missing_permissions",
                                   f"Couldn't remove having chat_id '{chat_id}' from database", ex)

                        return False

            except (Exception, psycopg2.DatabaseError) as ex:
                Logger.log("exception", "ChatTable.set_missing_permissions",
                           f"Couldn't get data of chat having chat_id '{chat_id}' from database", ex)

                return False

        else:
            Logger.log("error", "ChatTable.set_missing_permissions",
                       f"Couldn't get cursor required to remove chat having id '{chat_id}'")

            return False

    @classmethod
    def remove_chat(cls, chat_id: int) -> bool:
        cursor, iscursor = Database.get_cursor()

        if iscursor:
            query = """
                DELETE FROM chat
                WHERE chat_id = %s
            """

            try:
                connection = Database.connection
                connection: psycopg2._psycopg.connection

                cursor.execute(query, (chat_id,))

                connection.commit()

                return True

            except (Exception, psycopg2.DatabaseError) as ex:
                Logger.log("exception", "ChatTable.remove_chat",
                           f"Couldn't remove having chat_id '{chat_id}' from database", ex)

                return False

        else:
            Logger.log("error", "ChatTable.remove_chat",
                       f"Couldn't get cursor required to remove chat having id '{chat_id}'")

            return False

    @classmethod
    def get_chat_data(cls, chat_id: int, cursor: psycopg2._psycopg.cursor = None) -> (dict, bool):
        chat_data = {}

        if cursor is None:
            cursor, is_cursor = Database.get_cursor()

            if not is_cursor:
                Logger.log("error", "ChatTable.get_chat_data",
                           f"Couldn't get cursor required to get data of chat having chat_id '{chat_id}'")

                return chat_data, False

        cursor.execute("SELECT * FROM chat WHERE chat_id = %s", (chat_id,))

        column_names = [desc[0] for desc in cursor.description]
        record = cursor.fetchone()

        chat_data = Database.record_to_dict(column_names, record)

        return chat_data, bool(record)

    @classmethod
    async def fetch_chat(cls, bot_instance: telegram.Bot, chat_id: int, chat_data: dict = None, cursor: psycopg2._psycopg.cursor = None, migrating_from_chat_id: int = None) -> (dict, dict | None, bool):
        if cursor is None:
            cursor, iscursor = Database.get_cursor()

        if not cursor:
            Logger.log("error", "ChatTable.fetch_chat",
                       f"Couldn't get cursor required to get saved data for chat having chat_id '{chat_id}'")

        if not chat_data:
            chat_data = {}

            if cursor:
                try:
                    chat_data, _ = cls.get_chat_data(chat_id, cursor)

                except (Exception, psycopg2.DatabaseError) as ex:
                    Logger.log("exception", "ChatTable.fetch_chat",
                               f"Couldn't get data from database about chat having chat_id '{chat_id}'", ex)

        try:
            try:
                bot_member = await bot_instance.get_chat_member(chat_id, bot_instance.id)

                chat = await bot_instance.getChat(chat_id)

            except telegram.error.RetryAfter as ex:
                Logger.log("exception", "ChatTable.fetch_chat",
                           f"RetryAfter occurred while getting chat having id '{chat_id}'", ex)

                time.sleep(ex.retry_after + random.uniform(1, 2))

                bot_member = await bot_instance.get_chat_member(chat_id, bot_instance.id)

                chat = await bot_instance.getChat(chat_id)

        except telegram.error.ChatMigrated as ex:
            new_chat_id = ex.new_chat_id

            Logger.log("info", "ChatTable.fetch_chat",
                       f"The group having chat_id = '{chat_id}'"
                       f" migrated to a supergroup with chat_id = '{new_chat_id}'")

            migrated = ChatTable.migrate_chat_id(chat_id, new_chat_id)

            # If it was correctly migrated by the ChatTable.migrate_chat_id method a record associated to the
            # previous chat_id will no longer exists. The case in which it may not be migrated[*] correctly is
            # assumed to be the case where there is no record associated with the new chat_id. In that case,
            # we pass the previous chat_id as an argument to the new function call so that it will then fall
            # into one of the following two cases:
            #
            # - The supergroup is a group from which the bot has been kicked (-> the record associated with
            #   the previous chat_id gets deleted), e.g. because the group was immediately deleted by its owner
            #   after the migration and the bot didn't notice that (e.g. it was offline at that time);
            #
            # - The supergroup is a valid group, an entry with the new chat_id is added to the database,
            #   the migration[*] occurs (and is assumed to be successful this time), and then the record
            #   related to the previous chat_id gets finally deleted[*]
            #
            # [*] with the ChatTable.migrate_chat_id method

            if migrated:
                return cls.fetch_chat(bot_instance, new_chat_id, chat_data, cursor)
            else:
                return cls.fetch_chat(bot_instance, new_chat_id, chat_data, cursor, migrating_from_chat_id=chat_id)

        except telegram.error.Forbidden as ex:
            if "bot was kicked from the supergroup chat" in ex.message:
                Logger.log("info", "ChatTable.fetch_chat",
                           f"The bot was kicked from the group with chat_id = '{chat_id}'")

                if chat_data:
                    ChatTable.remove_chat(chat_id)

                if migrating_from_chat_id:
                    ChatTable.remove_chat(migrating_from_chat_id)

                return chat_data, None, True

            else:
                Logger.log("exception", "ChatTable.fetch_chat",
                           f"Couldn't get chat having chat_id '{chat_id}'", ex)

                return chat_data, None, False

        except Exception as ex:
            Logger.log("exception", "ChatTable.fetch_chat",
                       f"Couldn't get chat having chat_id '{chat_id}'", ex)

            return chat_data, None, False

        chat: telegram.Chat

        current_title = chat.title

        current_missing_permissions = False

        if not isinstance(bot_member, ChatMemberAdministrator):
            current_missing_permissions = True

        elif isinstance(bot_member, ChatMemberAdministrator):
            bot_member: ChatMemberAdministrator

            if not bot_member.can_invite_users:
                current_missing_permissions = True

        current_invite_link = chat.invite_link

        current_chat_admins = []

        chat_admins = None

        try:
            chat_admins = await bot_instance.get_chat_administrators(chat_id)

        except telegram.error.RetryAfter as ex:
            Logger.log("exception", "ChatTable.fetch_chat",
                       f"RetryAfter occurred while getting chat administrators for chat having id '{chat_id}'", ex)

            time.sleep(ex.retry_after + random.uniform(1, 2))

            chat_admins = await bot_instance.get_chat_administrators(chat_id)

        if chat_admins:
            for admin in chat_admins:
                admin: telegram.ChatMember

                current_chat_admins.append(admin.user.id)

        new_chat_data = {"chat_id": chat_id, "title": current_title, "invite_link": current_invite_link,
                         "chat_admins": current_chat_admins, "missing_permissions": current_missing_permissions}

        #

        if chat_data:
            saved_title = chat_data["title"]

            saved_invite_link = chat_data["invite_link"]

            saved_chat_admins = chat_data["chat_admins"]

            saved_missing_permissions = chat_data["missing_permissions"]

        if not chat_data or ([current_chat_admins] != saved_chat_admins or current_title != saved_title or current_invite_link != saved_invite_link or current_missing_permissions != saved_missing_permissions):
            query_vars = (current_title, current_invite_link, current_chat_admins, current_missing_permissions, chat_id)

            if chat_data:
                query = """
                    UPDATE chat
                    SET 
                        title = %s,
                        invite_link = %s,
                        chat_admins = %s,
                        missing_permissions = %s
                    WHERE chat_id = %s;
                """

                saved_values = (saved_title, saved_invite_link, saved_chat_admins, saved_missing_permissions, chat_id)

                Logger.log("debug", "ChatTable.fetch_chat", f"Old (saved) values: {saved_values}")
                Logger.log("debug", "ChatTable.fetch_chat", f"New (current) values: {query_vars}")
            else:
                query = """
                    INSERT INTO chat (title, invite_link, chat_admins, missing_permissions, chat_id)
                    VALUES (%s, %s, %s, %s, %s)
                """

            try:
                connection = Database.connection
                connection: psycopg2._psycopg.connection

                cursor.execute(query, query_vars)

                connection.commit()

                if chat_data:
                    if chat_data["directory_id"] is not None and current_missing_permissions != saved_missing_permissions:
                        directory_id = chat_data["directory_id"]

                        if current_missing_permissions:
                            DirectoryTable.increment_chats_count(directory_id, -1)

                        else:
                            DirectoryTable.increment_chats_count(directory_id, +1)

                    Logger.log("debug", "ChatTable.fetch_chat", f"Succesfully updated chat '{chat_id}' info")
                else:
                    if migrating_from_chat_id:
                        ChatTable.migrate_chat_id(migrating_from_chat_id, chat_id)

                    Logger.log("debug", "ChatTable.fetch_chat", f"Succesfully added chat '{chat_id}' info to database")

            except (Exception, psycopg2.DatabaseError) as ex:
                if chat_data:
                    Logger.log("exception", "ChatTable.fetch_chat", f"Couldn't update chat '{chat_id}'", ex)
                else:
                    Logger.log("exception", "ChatTable.fetch_chat", f"Couldn't add chat '{chat_id}'", ex)

                return chat_data, new_chat_data, False

        return chat_data, new_chat_data, True

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

            chats = Database.records_to_dict(column_names, records)

            for chat_id, chat_data in chats.items():
                await cls.fetch_chat(bot_instance, chat_id, chat_data, cursor)

                time.sleep(1)

        else:
            Logger.log("error", "ChatTable.fetch_chats", f"Couldn't get cursor required to fetch chats")


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
                Logger.log("critical", "SessionTable.add_session",
                           f"An exception occurred while trying to insert '{latest_menu_message_id}' "
                           f"latest_menu_message_id in 'session' table for '{chat_id}'", ex)

        else:
            Logger.log("error", "SessionTable.add_session", f"Couldn't get cursor required to insert session data")

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
                Logger.log("critical", "SessionTable.update_session",
                           f"An exception occurred while trying to update latest_menu_message_id for "
                           f"'{chat_id}' to `{new_latest_menu_message_id}'", ex)

        else:
            Logger.log("error", "SessionTable.update_session", f"Couldn't get cursor required to update session data")

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
                Logger.log("critical", "SessionTable.expire_old_sessions",
                           f"An exception occurred while trying to expire old sessions", ex)

        else:
            Logger.log("error", "SessionTable.expire_old_sessions",
                       f"Couldn't get cursor required to expire old sessions")


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
                           f"An exception occurred while trying to add '{key}' with value '{value}'", ex)
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
                           f"An exception occurred while trying to update '{key}' value to '{new_value}'", ex)
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
                           f"An exception occurred while trying to get '{key}' value", ex)
        else:
            Logger.log("error", "PersistentVarsTable.get_value_by_key",
                       f"Couldn't get cursor required to get '{key}' value")

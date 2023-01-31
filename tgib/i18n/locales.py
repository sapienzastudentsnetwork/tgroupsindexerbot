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

import os
from json     import load   as json_load
from os.path  import isfile as file_exists


class Locale:
    lang_codes    = ["it", "en"]
    def_lang_code = "en"
    locales       = {}

    def __init__(self, lang_code):
        if lang_code in self.lang_codes:
            self.lang_code = lang_code
        else:
            self.lang_code = self.def_lang_code

    @classmethod
    def init_locales(cls) -> None:
        for lang_code in cls.lang_codes:
            if lang_code != "df":
                json_path = os.path.join(os.path.dirname(__file__), f"{lang_code}.json")

                if file_exists(json_path):
                    with open(json_path, 'r') as json_file:
                        cls.locales[lang_code] = json_load(json_file)

    def parse_string_placeholders(self, string: str) -> str:
        start_index = 0

        var_start_tag = "<%"
        var_end_tag   = "%>"

        while start_index != -1:
            start_index = string.find(var_start_tag)

            if start_index != -1:
                end_index = string.find(var_end_tag)

                if end_index != -1:
                    placeholder = string[start_index:end_index+len(var_end_tag)]

                    string = string.replace(placeholder,
                                            self.get_string(placeholder[len(var_start_tag):-len(var_end_tag)]))
                else:
                    break

        return string

    def get_string(self, key: str) -> str:
        locale_dict = self.locales[self.lang_code]

        if key in locale_dict:
            string = locale_dict[key]

            if type(locale_dict[key]) == list:
                string = ''.join(string)

            return self.parse_string_placeholders(string)
        else:
            if self.lang_code != self.def_lang_code:
                df_locale_dict = self.locales[self.def_lang_code]

                if key in df_locale_dict:
                    return self.parse_string_placeholders(df_locale_dict[key])

            return locale_dict["i18n.string_not_found"].replace("[key]", key)

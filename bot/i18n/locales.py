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

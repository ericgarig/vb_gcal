import json
from datetime import datetime, timezone

import yaml


class Config:
    def __init__(self):
        self.config = None

    def read_config(self, file_path):
        """Read config file."""
        with open(file_path, "r") as stream:
            try:
                self.config = yaml.safe_load(stream)
                return self.config
            except yaml.YAMLError as e:
                print(e)

    def read_creds(self):
        """Read credentials file."""
        with open(self.cnf_value("calendar.token_path")) as json_file:
            data = json.load(json_file)
        return data

    def get_email_list(self) -> list:
        """Get list of teammate emails."""
        data = []
        with open(self.cnf_value("calendar.email_path"), "r") as f:
            data = f.readlines()
            data = [i.strip() for i in data]
        return data

    def cnf_value(self, path: str, sub_dict=None) -> str:
        """Get value of dot-delimited config path."""
        if not path:
            return ""
        [path, remaining] = path.split(".", 1) if path.count(".") else [path, None]
        working_dict = sub_dict if sub_dict else self.config
        sub_dict = working_dict.get(path)
        if remaining:
            return self.cnf_value(remaining, sub_dict)
        return sub_dict

    def cnf_list(self, path: str, delim=","):
        return self.cnf_value(path).split(delim)

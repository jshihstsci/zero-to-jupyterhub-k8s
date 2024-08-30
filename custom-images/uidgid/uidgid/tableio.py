import os
import yaml
import warnings


class TableIO:
    """
    Input and output of users/groups information table. Information can transition between three formats
    1. String - Initial base comes from EtcPasswd_Base and EtcGroups_Base string
        Once users and groups are updated, a new string can be obtained and passed to the spawner as /etc/passwd and /etc/groups file
        The string does not contain all the information in the table, only what's needed for the /etc/passwd and /etc/groups files
    2. Dictionary - Information in the dictionary can be actively manipulated, users and groups info can be added/deleted/modified
    3. YAML - The full table is stored in a YAML file that can be backed up in EFS or S3
    """

    def __init__(self, file_str=None, str_attr=[], yaml_filename="default.yaml"):
        self.file_str = file_str
        self.file_dict = None
        self.str_attr = (
            str_attr  # attributes to include in string for /etc/passwd and /etc/group
        )
        self.yaml_filename = yaml_filename

    def from_string(self, reset_file_dict=False):
        # Convert string to dictionary
        # If reset_file_dict set to True, this will overwirte any existing self.file_dict
        # Example for /etc/passwd
        # {"entries":[{"username":"root","password":"x","uid":"0","gid":"0","descr":"root","home":"/root","shell":"/bin/bash"}, \
        #             {"username":"daemon","password":"x","uid":"1","gid":"1","descr":"daemon","home":"/usr/sbin","shell":"/usr/sbin/nologin"}
        #           ...]}
        if self.file_str != None and len(self.str_attr) > 0:
            if self.file_dict == None or reset_file_dict == True:
                entry_list = list()
                for line in self.file_str.split("\n"):
                    entry_dict = dict()
                    entry_info = line.split(":")
                    for i in range(len(self.str_attr)):
                        entry_dict[self.str_attr[i]] = entry_info[i]
                    entry_list.append(entry_dict)
                self.file_dict = {"entries": entry_list}
            elif self.file_dict != None and reset_file_dict == False:
                warnings.warn(
                    f"File dictionary not empty and reset_file_dict set to False, will not replace with string content"
                )

    def to_string(self):
        # Convert file dictionary to string
        if self.file_dict != None:
            entry_list = self.file_dict["entries"]
            lines = list()
            for i in range(len(entry_list)):
                entry = entry_list[i]
                if (
                    "grouplist" in self.str_attr
                ):  # need to convert grouplist to comma seprated list of users
                    entry["grouplist"] = ",".join(entry["grouplist"])
                line = ":".join([entry[attr] for attr in self.str_attr])
                lines.append(line)
            self.file_str = "\n".join(lines)

    def write_yaml(self):
        with open(
            self.yaml_filename,
            "w",
        ) as f:
            yaml.dump(self.file_dict, f, sort_keys=False)

    def load_yaml(self):
        with open(
            self.yaml_filename,
            "r",
        ) as f:
            self.file_dict = yaml.safe_load(f)

    def get_file_string(self):
        self.load_yaml()
        self.to_string()
        return self.file_str

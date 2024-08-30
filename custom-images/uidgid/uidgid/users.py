"""Manages UNIX users, uids, /etc/passwd, user rosetta"""

import os
import yaml
import warnings

# from uidgid.types import UserRosettaRow, UserRosettaTable
from uidgid.types import (
    StsciEzid,
    StsciUuid,
    UserGid,
    UserUid,
    GroupGid,
    GroupAdminUid,
    UbuntuName,
    UserStatus,
    UserType,
    User,
)
from uidgid.base import EtcPasswd_Base, Base_Usernames
from uidgid.tableio import TableIO
from uidgid.username import to_valid_username


class EtcPasswd(TableIO):
    """
    TableIO for the /etc/passwd file
    """

    def __init__(
        self,
        file_str=EtcPasswd_Base,
        yaml_filename="etc_passwd.yaml",
        str_attr=["username", "password", "uid", "gid", "descr", "home", "shell"],
    ):
        super().__init__(
            file_str=file_str, yaml_filename=yaml_filename, str_attr=str_attr
        )


class StsciUsers(EtcPasswd):
    """
    Adds STSCI attributes (uuid, ezid, user status) to the base attributes
    """

    def __init__(
        self,
        file_str=EtcPasswd_Base,
        yaml_filename="stsci_users.yaml",
    ):
        if os.path.isfile(yaml_filename):
            # Do not overwrite existing yaml file
            raise FileExistsError(
                f"YAML file {yaml_filename} exists, must not overwrite existing file."
            )
        super().__init__(file_str=file_str, yaml_filename=yaml_filename)
        self.from_string()
        self.add_stsci_attr_to_base()

    def add_stsci_attr_to_base(self):
        # Add placeholder STSCI attributes (uuid, ezid) to base users
        for i, entry in enumerate(self.file_dict["entries"]):
            if self.file_dict["entries"][i]["username"] in Base_Usernames:
                self.file_dict["entries"][i]["uuid"] = "None"
                self.file_dict["entries"][i]["ezid"] = "None"
                self.file_dict["entries"][i]["status"] = "active"
        self.write_yaml()


class Users(StsciUsers):
    """
    Add/delete/modify/retrieval of user records
    """

    def __init__(self, yaml_filename="all_users.yaml"):
        if os.path.isfile(yaml_filename):
            # If yaml file exists, don't overwrite it, init using a tmp file then delete it
            super().__init__(yaml_filename="tmp_users.yaml")
            os.remove("tmp_users.yaml")
            # Load existing yaml file
            self.yaml_filename = yaml_filename
            self.load_yaml()
        else:
            super().__init__(yaml_filename=yaml_filename)
        self.all_uids = list()
        self.all_uuids = list()
        self.all_ezids = list()
        self.all_usernames = list()

    def load_all_uids(self):
        self.load_yaml()
        self.all_uids = [int(entry["uid"]) for entry in self.file_dict["entries"]]

    def load_all_uuids(self):
        self.load_yaml()
        self.all_uuids = [entry["uuid"] for entry in self.file_dict["entries"]]

    def load_all_ezids(self):
        self.load_yaml()
        self.all_ezids = [entry["ezid"] for entry in self.file_dict["entries"]]

    def load_all_usernames(self):
        self.load_yaml()
        self.all_usernames = [entry["username"] for entry in self.file_dict["entries"]]

    def get_new_uid(self, usertype="individual"):
        self.load_all_uids()
        if usertype == "individual":
            # Create a user's individual UID
            new_uid = UserUid.min_id
            while new_uid in self.all_uids:
                new_uid += 1
            return UserUid(new_uid)
        if usertype == "group":
            # Create a group admin's UID
            new_uid = GroupAdminUid.min_id
            while new_uid in self.all_uids:
                new_uid += 1
            return GroupAdminUid(new_uid)

    def get_new_username(self, ezid, existing_names=None):
        # Create valid username from ezid, check for duplication
        self.load_all_usernames()
        existing_names = existing_names or self.all_usernames
        new_username = to_valid_username(
            ezid, existing_names=existing_names)
        return new_username

    def user_exist(self, id, id_type="uuid"):
        # Does user exist?
        if id_type == "uuid":
            self.load_all_uuids()
            user_exist = id in self.all_uuids
        elif id_type == "ezid":
            self.load_all_ezids()
            user_exist = id in self.all_ezids
        elif id_type == "username":
            self.load_all_usernames()
            user_exist = id in self.all_usernames
        else:
            raise ValueError(
                f"Invalid ID type {id_type}, must be uuid, ezid, or username"
            )
        return user_exist

    def add_user(
        self,
        uuid="00000000-0000-0000-0000-000000000000",
        ezid="",
        username=None,
        password="x",
        uid=None,
        gid=None,
        descr="",
        home=None,
        shell="/bin/bash",
        status="active",
        usertype="individual",
        existing_names=None,
    ):
        # Load yaml
        self.load_yaml()

        # Check whether user exist and essential values
        if self.user_exist(uuid) and uuid != "00000000-0000-0000-0000-000000000000":
            raise RuntimeError(f"User with UUID {uuid} already exists")

        if ezid == "" and username == None:
            # If no ezid is provided, username must be provided and vice versa
            raise Exception(f"Please provide an ezid or username")
        if username == None:
            username = self.get_new_username(ezid, existing_names=existing_names)
        if uid == None:
            uid = self.get_new_uid(usertype=usertype)
        if gid == None:
            gid = UserGid(uid)
            # raise Exception(f"Please provide a GID")

        home = home or f"/home/{username}"

        # Check value types
        if type(username) != UbuntuName:
            username = UbuntuName(username)
        if type(uuid) != StsciUuid:
            uuid = StsciUuid(uuid)
        if type(ezid) != StsciEzid:
            ezid = StsciEzid(ezid)
        if type(status) != UserStatus:
            status = UserStatus(status)
        if type(usertype) != UserType:
            usertype = UserType(usertype)
        if usertype == "individual":
            if type(uid) != UserUid:
                uid = UserUid(uid)
            if type(gid) != UserGid:
                gid = UserGid(gid)
        elif usertype == "group":
            if type(uid) != GroupAdminUid:
                uid = GroupAdminUid(uid)
            if type(gid) != GroupGid:
                gid = GroupGid(gid)

        # Update dictionary and write to yaml
        user_dict = dict()
        user_dict["username"] = str(username)
        user_dict["password"] = str(password)
        user_dict["uid"] = str(uid)
        user_dict["gid"] = str(gid)
        user_dict["descr"] = str(descr)
        user_dict["home"] = str(home)
        user_dict["shell"] = str(shell)
        user_dict["uuid"] = str(uuid)
        user_dict["ezid"] = str(ezid)
        user_dict["status"] = str(status)
        user_dict["usertype"] = str(usertype)

        self.file_dict["entries"].append(user_dict)
        self.write_yaml()

        # Construct and return User object
        user = User()
        user.uuid = uuid
        user.ezid = ezid
        user.username = username
        user.password = password
        user.uid = uid
        user.gid = gid
        user.descr = descr
        user.home = home
        user.shell = shell
        user.status = status
        user.usertype = usertype

        return user

    def delete_user(self, id, id_type="uuid"):
        # Set user status to deactivated
        id = str(id)
        self.load_yaml()
        for i, entry in enumerate(self.file_dict["entries"]):
            if entry[id_type] == id:
                self.file_dict["entries"][i]["status"] = "deactivated"
                break
        self.write_yaml()

    def get_etc_passwd_string(self):
        # Get all users for etc/passwd (includes inactive users)
        string = self.get_file_string()
        return string

    def get_active_user_string(self):
        # Convert active users in user dictionary to etc/passwd string
        self.load_yaml()
        lines = list()
        for i in range(len(self.file_dict["entries"])):
            user = self.file_dict["entries"][i]
            if user["status"] == "active":
                line = ":".join([user[attr] for attr in self.str_attr])
                lines.append(line)
        active_file_str = "\n".join(lines)
        return active_file_str

    def get_active_usernames(self):
        # Return username of all active users
        self.load_yaml()
        active_users = list()
        for i in range(len(self.file_dict["entries"])):
            user = self.file_dict["entries"][i]
            if user["status"] == "active":
                active_users.append(user["username"])
        return active_users

    def get_user_info(self, id, id_type="uuid"):
        # Return a User object given an UUID
        self.load_yaml()
        user = User()
        for entry in self.file_dict["entries"]:
            if entry[id_type] == str(id):
                user.uuid = StsciUuid(entry["uuid"])
                user.ezid = StsciEzid(entry["ezid"])
                user.username = UbuntuName(entry["username"])
                user.password = entry["password"]
                if entry["usertype"] == "individual":
                    user.uid = UserUid(int(entry["uid"]))
                    user.gid = UserGid(int(entry["gid"]))
                elif entry["usertype"] == "group":
                    user.uid = GroupAdminUid(int(entry["uid"]))
                    user.gid = GroupGid(int(entry["gid"]))
                else:
                    user.uid = int(entry["uid"])
                    user.gid = int(entry["gid"])
                user.descr = entry["descr"]
                user.home = entry["home"]
                user.shell = entry["shell"]
                user.status = UserStatus(entry["status"])
                user.usertype = UserType(entry["usertype"])
                break
        else:
            raise RuntimeError(f"User with {id_type} {id} not found")
        return user

    def user_active(self, id, id_type="uuid"):
        # Is user active?
        user = self.get_user_info(id, id_type)
        user_active = user.status == "active"
        return user_active

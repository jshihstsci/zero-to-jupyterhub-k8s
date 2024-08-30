"""Manages UNIX groups, gids, /etc/group, group rosetta"""

import os
import yaml
import warnings
from uidgid.base import EtcGroup_Base, Base_Groupnames
from uidgid.types import (
    UserGid,
    GroupGid,
    UbuntuName,
    TeamName,
    UserStatus,
    UserType,
    Group,
)
from uidgid.username import to_valid_username
from uidgid.tableio import TableIO


class EtcGroup(TableIO):
    """
    TableIO for the /etc/group file
    """

    def __init__(
        self,
        file_str=EtcGroup_Base,
        yaml_filename="etc_group.yaml",
        str_attr=["groupname", "password", "gid", "grouplist"],
    ):
        super().__init__(
            file_str=file_str, yaml_filename=yaml_filename, str_attr=str_attr
        )


class StsciGroups(EtcGroup):
    """
    Adds STSCI group attributes (teamname, user_type) to the base attributes
    """

    def __init__(
        self,
        file_str=EtcGroup_Base,
        yaml_filename="stsci_groups.yaml",
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
        # Add placeholder STSCI attributes (teamname, usertype) to base groups
        for i, entry in enumerate(self.file_dict["entries"]):
            if self.file_dict["entries"][i]["groupname"] in Base_Groupnames:
                self.file_dict["entries"][i]["teamname"] = self.file_dict["entries"][i]["groupname"]
                self.file_dict["entries"][i]["usertype"] = "group"
                self.file_dict["entries"][i]["status"] = "active"
        self.write_yaml()


class Groups(StsciGroups):
    """
    Add/delete/modify/retrieve group records
    """

    def __init__(self, yaml_filename="all_groups.yaml"):
        if os.path.isfile(yaml_filename):
            # If yaml file exists, don't overwrite it, init using a tmp file then delete it
            super().__init__(yaml_filename="tmp_group.yaml")
            if os.path.isfile("tmp_group.yaml"):
                os.remove("tmp_group.yaml")
            # Load existing yaml file
            self.yaml_filename = yaml_filename
            self.load_yaml()
        else:
            super().__init__(yaml_filename=yaml_filename)
        self.all_gids = list()
        self.all_teamnames = list()  # List of team names from uidgid inputs
        self.all_groupnames = (
            list()
        )  # List of valid ubuntu group names generated from input teamnames

    def load_all_gids(self):
        self.load_yaml()
        self.all_gids = [int(entry["gid"]) for entry in self.file_dict["entries"]]

    def load_all_groupnames(self):
        self.load_yaml()
        self.all_groupnames = [
            entry["groupname"] for entry in self.file_dict["entries"]
        ]

    def load_all_teamnames(self):
        self.load_yaml()
        self.all_teamnames = [entry["teamname"] for entry in self.file_dict["entries"]]

    def get_new_gid(self, usertype="individual"):
        self.load_all_gids()
        if usertype == "individual":
            # Create a user's individual personal GID
            new_gid = UserGid.min_id
            while new_gid in self.all_gids:
                new_gid += 1
            return UserGid(new_gid)
        if usertype == "group":
            # Create a group's GID
            new_gid = GroupGid.min_id
            while new_gid in self.all_gids:
                new_gid += 1
            return GroupGid(new_gid)

    def get_new_groupname(self, teamname, existing_names=None):
        self.load_all_groupnames()
        existing_names = existing_names or self.all_groupnames
        new_groupname = to_valid_username(
            teamname, existing_names=existing_names, kind="group")
        return new_groupname

    def create_new_group(
        self,
        teamname,
        groupname=None,
        password="x",
        gid=None,
        status="active",
        usertype="individual",
        existing_names=None,
    ):
        # Load yaml
        self.load_yaml()

        # Check whether team exists
        if self.team_exist(teamname):
            raise RuntimeError(f"Team {teamname} already exists.")

        if groupname == None:
            groupname = self.get_new_groupname(teamname, existing_names=existing_names)
        if gid is None:
            gid = self.get_new_gid(usertype=usertype)
        elif self.gid_exist(gid):
            raise RuntimeError(f"GID {gid} already exist.")

        # Check value types
        if usertype == "individual" and type(gid) != UserGid:
            gid = UserGid(gid)
        if usertype == "group" and type(gid) != GroupGid:
            gid = GroupGid(gid)
        if type(status) != UserStatus:
            status = UserStatus(status)
        if type(usertype) != UserType:
            usertype = UserType(usertype)
        if type(groupname) != UbuntuName:
            groupname = UbuntuName(groupname)

        # Update dictionary and write to yaml
        group_dict = dict()
        group_dict["teamname"] = str(teamname)
        group_dict["groupname"] = str(groupname)
        group_dict["password"] = str(password)
        group_dict["gid"] = str(gid)
        group_dict["grouplist"] = list()
        group_dict["status"] = str(status)
        group_dict["usertype"] = str(usertype)

        self.file_dict["entries"].append(group_dict)
        self.write_yaml()

        # Construct and return Group object
        group_info = Group()
        group_info.teamname = teamname
        group_info.groupname = groupname
        group_info.password = password
        group_info.gid = gid
        group_info.grouplist = list()
        group_info.status = status
        group_info.usertype = usertype

        return group_info

    def team_exist(self, teamname):
        # Does team exist?
        teamname = str(teamname)
        self.load_all_teamnames()
        team_exist = teamname in self.all_teamnames
        return team_exist

    def group_exist(self, groupname):
        # Does group exist?
        groupname = str(groupname)
        self.load_all_groupnames()
        group_exist = groupname in self.all_groupnames
        return group_exist

    def gid_exist(self, gid):
        # Does group exist?
        gid = int(gid)
        self.load_all_gids()
        gid_exist = gid in self.all_gids
        return gid_exist

    def group_active(self, groupname):
        # Is group active?
        self.load_yaml()
        for entry in self.file_dict["entries"]:
            if entry["groupname"] == groupname:
                group_active = entry["status"] == "active"
                break
        return group_active

    def delete_group(self, groupname):
        # Set team status to deactivated
        self.load_yaml()
        groupname = str(groupname)
        for i, entry in enumerate(self.file_dict["entries"]):
            if entry["groupname"] == groupname:
                self.file_dict["entries"][i]["status"] = "deactivated"
                break
        self.write_yaml()

    def lookup_gid(self, name, name_type="groupname"):
        # Return the gid (int) of a certain group/team name
        self.load_yaml()
        for entry in self.file_dict["entries"]:
            if entry[name_type] == name:
                gid = entry["gid"]
                break
        return int(gid)

    def is_user_in_group(self, username, groupname):
        # Is user in a given group?
        self.load_yaml()
        if not self.group_exist(groupname):
            raise Exception(f"Group {groupname} does not exist")
        for entry in self.file_dict["entries"]:
            if entry["groupname"] == groupname:
                user_in_group = username in entry["grouplist"]
                break
        return user_in_group

    def add_user_to_group(self, username, groupname):
        # Add user to a group's grouplist
        groupname = str(groupname)
        username = str(username)
        self.load_yaml()
        if not self.group_exist(groupname):
            raise ValueError(f"Group {groupname} does not exist")
        for i, entry in enumerate(self.file_dict["entries"]):
            if entry["groupname"] == groupname:
                if len(entry["grouplist"]) >= 32768:
                    raise RuntimeError(f"Too many users in group {groupname}.")
                if username not in entry["grouplist"]:
                    self.file_dict["entries"][i]["grouplist"].append(username)
                break
        self.write_yaml()

    def remove_user_from_group(self, username, groupname):
        # Remove user from a group's grouplist
        groupname = str(groupname)
        username = str(username)
        self.load_yaml()
        if not self.group_exist(groupname):
            raise Exception(f"Group {groupname} does not exist")
        for i, entry in enumerate(self.file_dict["entries"]):
            if entry["groupname"] == groupname:
                if username in entry["grouplist"]:
                    self.file_dict["entries"][i]["grouplist"].remove(username)
                break
        self.write_yaml()

    def remove_user_from_all_groups(self, username):
        # Remove a user from all groups' grouplists
        username = str(username)
        self.load_yaml()
        for i, entry in enumerate(self.file_dict["entries"]):
            if username in entry["grouplist"]:
                self.file_dict["entries"][i]["grouplist"].remove(username)
        self.write_yaml()

    def get_users_of_group(self, groupname):
        # Return a list of users of a group
        self.load_yaml()
        for entry in self.file_dict["entries"]:
            if entry["groupname"] == groupname:
                groups_users = entry["grouplist"]
                break
        return groups_users

    def get_groups_of_user(self, username):
        # Return a list of groups a user belong to
        self.load_yaml()
        user_groups = list()
        for entry in self.file_dict["entries"]:
            if username in entry["grouplist"]:
                user_groups.append(entry["groupname"])
        return user_groups

    def get_etc_group_string(self):
        # Get all groups in etc/group (includes inactive groups)
        string = self.get_file_string()
        return string

    def get_active_group_string(self):
        # Convert active groups in group dictionary to etc/group string
        self.load_yaml()
        lines = list()
        for i in range(len(self.file_dict["entries"])):
            group = self.file_dict["entries"][i]
            if group["status"] == "active":
                if (
                    "grouplist" in self.str_attr
                ):  # need to convert grouplist to comma seprated list of users
                    group["grouplist"] = ",".join(group["grouplist"])
                line = ":".join([group[attr] for attr in self.str_attr])
                lines.append(line)
        active_file_str = "\n".join(lines)
        return active_file_str

    def get_group_info(self, id, id_type="groupname"):
        # Return a Group object with all group attributes
        self.load_yaml()
        group_info = Group()
        for entry in self.file_dict["entries"]:
            if entry[id_type] == str(id):
                group_info.teamname = TeamName(entry["teamname"])
                group_info.groupname = UbuntuName(entry["groupname"])
                group_info.password = entry["password"]
                if entry["usertype"] == "individual":
                    group_info.gid = UserGid(int(entry["gid"]))
                elif entry["usertype"] == "group":
                    group_info.gid = GroupGid(int(entry["gid"]))
                else:
                    group_info.gid = int(entry["gid"])
                group_info.grouplist = entry["grouplist"]
                group_info.status = UserStatus(entry["status"])
                group_info.usertype = UserType(entry["usertype"])
                break
        else:
            raise RuntimeError(f"Group {id} does not exist.")
        return group_info

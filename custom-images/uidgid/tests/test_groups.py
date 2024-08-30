"""Manages UNIX groups, gids, /etc/group, group rosetta"""

import os
import pytest
from uidgid.groups import Groups
from uidgid.types import UserGid, GroupGid

Test_Group_Yaml_Filename = "tmp_test_all_groups.yaml"


def cleanup_test_yaml_files():
    if os.path.isfile(Test_Group_Yaml_Filename):
        os.remove(Test_Group_Yaml_Filename)


def setup_test_groups():
    cleanup_test_yaml_files()
    groups = Groups(yaml_filename=Test_Group_Yaml_Filename)
    return groups


def add_many_test_groups_and_users(groups):
    # Create new groups and add users
    groups.create_new_group("group1")
    groups.add_user_to_group("user1", "group1")
    groups.add_user_to_group("user2", "group1")
    groups.add_user_to_group("user3", "group1")
    groups.create_new_group("group2", usertype="group")
    groups.add_user_to_group("user1", "group2")
    groups.add_user_to_group("user2", "group2")
    groups.add_user_to_group("user3", "group2")
    groups.add_user_to_group("user4", "group2")
    groups.add_user_to_group("user5", "group2")
    groups.create_new_group("group3")
    groups.add_user_to_group("user3", "group3")
    groups.add_user_to_group("user4", "group3")
    groups.add_user_to_group("user5", "group3")
    return groups


def test_add_groups():
    groups = setup_test_groups()

    # Get a list of GIDs before creating new groups
    groups.load_all_gids()
    all_gids_before = groups.all_gids.copy()

    # Crate new groups, check that they exist, are active, and have correct group names
    group1_info = groups.create_new_group("group1", usertype="individual")
    group2_info = groups.create_new_group("group2", usertype="group")

    assert groups.group_exist("group1") == True
    assert groups.group_exist("group2") == True
    assert groups.group_active("group1") == True
    assert groups.group_active("group2") == True
    assert group1_info.groupname == "group1"
    assert group2_info.groupname == "group2"

    # Check that the GIDs are new, , and in the expected range
    assert group1_info.gid not in all_gids_before
    assert group2_info.gid not in all_gids_before
    assert group1_info.gid >= UserGid.min_id and group1_info.gid <= UserGid.max_id
    assert group2_info.gid >= GroupGid.min_id and group2_info.gid <= GroupGid.max_id


def test_delete_groups():
    # Create a new group and make sure that it's active
    groups = setup_test_groups()
    groups.create_new_group("group1")
    assert groups.group_active("group1") == True

    # Delete the group and check that it's deactivated
    groups.delete_group("group1")
    assert groups.group_active("group1") == False


def test_add_users_to_groups():
    # Create a new group and add some users
    groups = setup_test_groups()
    groups.create_new_group("group1")
    groups.add_user_to_group("user1", "group1")
    groups.add_user_to_group("user2", "group1")
    groups.add_user_to_group("user3", "group1")

    # Get list of users for the group, check that it contains all the added users
    group_users = groups.get_users_of_group("group1")
    assert group_users == ["user1", "user2", "user3"]


def test_remove_users_from_groups():
    # Create new groups and add users
    groups = setup_test_groups()
    groups = add_many_test_groups_and_users(groups)

    # Check the users of group1
    group1_users = groups.get_users_of_group("group1")
    assert group1_users == ["user1", "user2", "user3"]

    # Remove user1 from group1 and recheck group members
    groups.remove_user_from_group("user1", "group1")
    group1_users = groups.get_users_of_group("group1")
    assert group1_users == ["user2", "user3"]

    # Check that user3 is in all three groups
    user3_groups = groups.get_groups_of_user("user3")
    assert user3_groups == ["group1", "group2", "group3"]

    # Remove user3 from all groups and check that it's removed
    groups.remove_user_from_all_groups("user3")
    user3_groups = groups.get_groups_of_user("user3")
    assert len(user3_groups) == 0
    

def test_lookup_gid():
    # Create new groups and add users
    groups = setup_test_groups()
    groups = add_many_test_groups_and_users(groups)

    group1_gid = int(groups.lookup_gid('group1'))
    group2_gid = int(groups.lookup_gid('group2'))
    group3_gid = int(groups.lookup_gid('group3'))

    assert group1_gid == 1000
    assert group2_gid == 60000
    assert group3_gid == 1001


def test_get_etc_group_strings():
    # Create new groups, add users, and delete a group
    groups = setup_test_groups()
    groups = add_many_test_groups_and_users(groups)
    groups.delete_group("group1")

    # Get /etc/group string and check that it matches expectation
    ect_group_string = groups.get_etc_group_string()
    assert ect_group_string == expected_etc_group_string

    # Get /etc/group string for active groups and check that it matches expectation
    ect_active_group_string = groups.get_active_group_string()
    assert ect_active_group_string == expected_etc_active_group_string


expected_etc_group_string = "root:x:0:\n\
daemon:x:1:\n\
bin:x:2:\n\
sys:x:3:\n\
adm:x:4:\n\
tty:x:5:\n\
disk:x:6:\n\
lp:x:7:\n\
mail:x:8:\n\
news:x:9:\n\
uucp:x:10:\n\
man:x:12:\n\
proxy:x:13:\n\
kmem:x:15:\n\
dialout:x:20:\n\
fax:x:21:\n\
voice:x:22:\n\
cdrom:x:24:\n\
floppy:x:25:\n\
tape:x:26:\n\
sudo:x:27:\n\
audio:x:29:\n\
dip:x:30:\n\
www-data:x:33:\n\
backup:x:34:\n\
operator:x:37:\n\
list:x:38:\n\
irc:x:39:\n\
src:x:40:\n\
gnats:x:41:\n\
shadow:x:42:\n\
utmp:x:43:\n\
video:x:44:\n\
sasl:x:45:\n\
plugdev:x:46:\n\
staff:x:50:\n\
games:x:60:\n\
users:x:100:\n\
nogroup:x:65534:\n\
ssh:x:101:\n\
systemd-timesync:x:102:\n\
systemd-journal:x:103:\n\
systemd-network:x:104:\n\
systemd-resolve:x:105:\n\
crontab:x:106:\n\
messagebus:x:107:\n\
group1:x:1000:user1,user2,user3\n\
group2:x:60000:user1,user2,user3,user4,user5\n\
group3:x:1001:user3,user4,user5\n".strip()

expected_etc_active_group_string = "root:x:0:\n\
daemon:x:1:\n\
bin:x:2:\n\
sys:x:3:\n\
adm:x:4:\n\
tty:x:5:\n\
disk:x:6:\n\
lp:x:7:\n\
mail:x:8:\n\
news:x:9:\n\
uucp:x:10:\n\
man:x:12:\n\
proxy:x:13:\n\
kmem:x:15:\n\
dialout:x:20:\n\
fax:x:21:\n\
voice:x:22:\n\
cdrom:x:24:\n\
floppy:x:25:\n\
tape:x:26:\n\
sudo:x:27:\n\
audio:x:29:\n\
dip:x:30:\n\
www-data:x:33:\n\
backup:x:34:\n\
operator:x:37:\n\
list:x:38:\n\
irc:x:39:\n\
src:x:40:\n\
gnats:x:41:\n\
shadow:x:42:\n\
utmp:x:43:\n\
video:x:44:\n\
sasl:x:45:\n\
plugdev:x:46:\n\
staff:x:50:\n\
games:x:60:\n\
users:x:100:\n\
nogroup:x:65534:\n\
ssh:x:101:\n\
systemd-timesync:x:102:\n\
systemd-journal:x:103:\n\
systemd-network:x:104:\n\
systemd-resolve:x:105:\n\
crontab:x:106:\n\
messagebus:x:107:\n\
group2:x:60000:user1,user2,user3,user4,user5\n\
group3:x:1001:user3,user4,user5\n".strip()

"""Manages UNIX users, uids, /etc/passwd, user rosetta"""

import os
import pytest
from uidgid.users import Users
from uidgid.types import UserUid, GroupAdminUid
from uidgid.base import Base_UIDs, Base_Usernames

Test_User1 = {
    "uuid": "abcdabcd-a234-b678-c0ab-abcd1234abcd",
    "ezid": "ezid-üser1@stsci.edu",
    "home": "/home/user1",
    "expected_username": "ezid-user1",
}
Test_User2 = {
    "uuid": "aabbccdd-d123-e456-f789-1234abcd1234",
    "ezid": "ezid:user2",
    "home": "/home/user2",
    "expected_username": "eziduser2",
}
Test_User_GroupAdmin = {"username": "test-group-admin", "home": "/home/testgroupadmin", "expected_username": "test-group-admin"}
Test_User_Yaml_Filename = "tmp_test_all_users.yaml"


def cleanup_test_yaml_files():
    if os.path.isfile(Test_User_Yaml_Filename):
        os.remove(Test_User_Yaml_Filename)


def setup_test_users():
    cleanup_test_yaml_files()
    users = Users(yaml_filename=Test_User_Yaml_Filename)
    return users

def add_test_users(users):
    # Add two test users, one indiviudal and one group user
    users.add_user(
        Test_User1["uuid"],
        Test_User1["ezid"],
        gid=1001,
        home=Test_User1["home"],
        usertype="individual",
    )
    users.add_user(
        Test_User2["uuid"],
        Test_User2["ezid"],
        gid=1002,
        home=Test_User2["home"],
        usertype="individual",
    )
    users.add_user(
        username=Test_User_GroupAdmin["username"],
        home=Test_User_GroupAdmin["home"],
        gid=60000,
        usertype="group",
    )
    return users

def test_add_user():
    """Test creating new users"""
    users = setup_test_users()

    # Add the test users, get user info, and check that all the attributes are as expected
    users = add_test_users(users)

    added_indv_user_info = users.get_user_info(Test_User1["uuid"])
    added_group_user_info = users.get_user_info(Test_User_GroupAdmin["username"], id_type="username")
    active_users = users.get_active_usernames()

    assert added_indv_user_info.username == Test_User1["expected_username"]
    assert added_indv_user_info.home == Test_User1["home"]
    assert added_indv_user_info.uuid == Test_User1["uuid"]
    assert added_indv_user_info.status == "active"
    assert added_indv_user_info.username in active_users
    assert added_indv_user_info.usertype == "individual"

    assert users.user_exist(Test_User1["uuid"]) == True
    assert users.user_exist(Test_User1["ezid"], id_type="ezid") == True
    assert users.user_exist(Test_User1["expected_username"], id_type="username") == True
    assert users.user_active(Test_User1["uuid"]) == True
    assert users.user_active(Test_User1["ezid"], id_type="ezid") == True
    assert users.user_active(Test_User1["expected_username"], id_type="username") == True

    assert added_group_user_info.username == Test_User_GroupAdmin["expected_username"]
    assert added_group_user_info.home == Test_User_GroupAdmin["home"]
    assert added_group_user_info.status == "active"
    assert added_group_user_info.username in active_users
    assert added_group_user_info.usertype == "group"

    assert added_indv_user_info.uid == 1001
    assert added_group_user_info.uid == 60000

    cleanup_test_yaml_files()


def test_lookup_id_types():
    """Test looking up users with different ID types (uuid, ezid, username)"""
    users = setup_test_users()
    users = add_test_users(users)

    assert users.user_exist(Test_User1["uuid"]) == True
    assert users.user_exist(Test_User1["ezid"], id_type="ezid") == True
    assert users.user_exist(Test_User1["expected_username"], id_type="username") == True
    assert users.user_active(Test_User1["uuid"]) == True
    assert users.user_active(Test_User1["ezid"], id_type="ezid") == True
    assert users.user_active(Test_User1["expected_username"], id_type="username") == True

    user_info_uuid = users.get_user_info(Test_User1["uuid"])
    user_info_ezid = users.get_user_info(Test_User1["ezid"], id_type="ezid")
    user_info_username = users.get_user_info(Test_User1["expected_username"], id_type="username")

    assert user_info_uuid.uuid == user_info_ezid.uuid
    assert user_info_uuid.uuid == user_info_username.uuid

    cleanup_test_yaml_files()


def test_user_lists():
    """Test thet all_uids, all_uuids, all_ezids, all_usernames lists"""
    users = setup_test_users()
    users = add_test_users(users)
    users.load_all_uids()
    users.load_all_uuids()
    users.load_all_ezids()
    users.load_all_usernames()

    all_uids = users.all_uids
    all_uuids = users.all_uuids
    all_ezids = users.all_ezids
    all_usernames = users.all_usernames

    expected_uids = Base_UIDs
    expected_uids.extend([1001, 1002, 60000])
    expected_usernames = Base_Usernames
    expected_usernames.extend(['ezid-user1', 'eziduser2', 'test-group-admin'])

    all_uids.sort()
    all_usernames.sort()
    expected_uids.sort()
    expected_usernames.sort()
    
    assert all_uids == expected_uids
    assert all_usernames == expected_usernames
    assert Test_User1["uuid"] in all_uuids
    assert Test_User1["ezid"] in all_ezids
    assert Test_User2["uuid"] in all_uuids
    assert Test_User2["ezid"] in all_ezids

    cleanup_test_yaml_files()

def test_get_new_uid():
    users = setup_test_users()
    new_indv_uid = users.get_new_uid(usertype="individual")
    new_group_admin_uid = users.get_new_uid(usertype="group")
    
    assert int(new_indv_uid) == 1001
    assert int(new_group_admin_uid) == 60000

    cleanup_test_yaml_files()

def test_delete_user():
    """Test deleting a user"""
    users = setup_test_users()
    users = add_test_users(users)

    # Check an added user and make sure that it's active
    assert users.user_active(Test_User2["uuid"]) == True

    # Delete the user and check that it's deactivated
    users.delete_user(Test_User2["uuid"])
    deleted_user = users.get_user_info(Test_User2["uuid"])
    active_users = users.get_active_usernames()

    assert deleted_user.status == "deactivated"
    assert users.user_active(Test_User2["uuid"]) == False
    assert deleted_user.username not in active_users

    cleanup_test_yaml_files()


def test_get_etc_passwd_strings():
    """Test getting the /ect/passwd strings"""
    users = setup_test_users()
    users = add_test_users(users)

    # Delete (set to inactive) one of the users 
    users.delete_user(Test_User2["uuid"])

    all_user_ect_passwd = users.get_etc_passwd_string()
    active_user_ect_passwd = users.get_active_user_string()
    assert all_user_ect_passwd == expected_all_user_ect_passwd
    assert active_user_ect_passwd == expected_active_user_ect_passwd

    cleanup_test_yaml_files()


expected_all_user_ect_passwd = "root:x:0:0:root:/root:/bin/bash\n\
daemon:x:1:1:daemon:/usr/sbin:/usr/sbin/nologin\n\
bin:x:2:2:bin:/bin:/usr/sbin/nologin\n\
sys:x:3:3:sys:/dev:/usr/sbin/nologin\n\
sync:x:4:65534:sync:/bin:/bin/sync\n\
games:x:5:60:games:/usr/games:/usr/sbin/nologin\n\
man:x:6:12:man:/var/cache/man:/usr/sbin/nologin\n\
lp:x:7:7:lp:/var/spool/lpd:/usr/sbin/nologin\n\
mail:x:8:8:mail:/var/mail:/usr/sbin/nologin\n\
news:x:9:9:news:/var/spool/news:/usr/sbin/nologin\n\
uucp:x:10:10:uucp:/var/spool/uucp:/usr/sbin/nologin\n\
proxy:x:13:13:proxy:/bin:/usr/sbin/nologin\n\
www-data:x:33:33:www-data:/var/www:/usr/sbin/nologin\n\
backup:x:34:34:backup:/var/backups:/usr/sbin/nologin\n\
list:x:38:38:Mailing List Manager:/var/list:/usr/sbin/nologin\n\
irc:x:39:39:ircd:/var/run/ircd:/usr/sbin/nologin\n\
gnats:x:41:41:Gnats Bug-Reporting System (admin):/var/lib/gnats:/usr/sbin/nologin\n\
nobody:x:65534:65534:nobody:/nonexistent:/usr/sbin/nologin\n\
_apt:x:100:65534::/nonexistent:/usr/sbin/nologin\n\
jovyan:x:1000:100::/home/jovyan:/bin/bash\n\
systemd-timesync:x:101:102:systemd Time Synchronization,,,:/run/systemd:/usr/sbin/nologin\n\
systemd-network:x:102:104:systemd Network Management,,,:/run/systemd:/usr/sbin/nologin\n\
systemd-resolve:x:103:105:systemd Resolver,,,:/run/systemd:/usr/sbin/nologin\n\
sshd:x:104:65534::/run/sshd:/usr/sbin/nologin\n\
messagebus:x:105:107::/nonexistent:/usr/sbin/nologin\n\
ezid-user1:x:1001:1001::/home/user1:/bin/bash\n\
eziduser2:x:1002:1002::/home/user2:/bin/bash\n\
test-group-admin:x:60000:60000::/home/testgroupadmin:/bin/bash\n".strip()

expected_active_user_ect_passwd = "root:x:0:0:root:/root:/bin/bash\n\
daemon:x:1:1:daemon:/usr/sbin:/usr/sbin/nologin\n\
bin:x:2:2:bin:/bin:/usr/sbin/nologin\n\
sys:x:3:3:sys:/dev:/usr/sbin/nologin\n\
sync:x:4:65534:sync:/bin:/bin/sync\n\
games:x:5:60:games:/usr/games:/usr/sbin/nologin\n\
man:x:6:12:man:/var/cache/man:/usr/sbin/nologin\n\
lp:x:7:7:lp:/var/spool/lpd:/usr/sbin/nologin\n\
mail:x:8:8:mail:/var/mail:/usr/sbin/nologin\n\
news:x:9:9:news:/var/spool/news:/usr/sbin/nologin\n\
uucp:x:10:10:uucp:/var/spool/uucp:/usr/sbin/nologin\n\
proxy:x:13:13:proxy:/bin:/usr/sbin/nologin\n\
www-data:x:33:33:www-data:/var/www:/usr/sbin/nologin\n\
backup:x:34:34:backup:/var/backups:/usr/sbin/nologin\n\
list:x:38:38:Mailing List Manager:/var/list:/usr/sbin/nologin\n\
irc:x:39:39:ircd:/var/run/ircd:/usr/sbin/nologin\n\
gnats:x:41:41:Gnats Bug-Reporting System (admin):/var/lib/gnats:/usr/sbin/nologin\n\
nobody:x:65534:65534:nobody:/nonexistent:/usr/sbin/nologin\n\
_apt:x:100:65534::/nonexistent:/usr/sbin/nologin\n\
jovyan:x:1000:100::/home/jovyan:/bin/bash\n\
systemd-timesync:x:101:102:systemd Time Synchronization,,,:/run/systemd:/usr/sbin/nologin\n\
systemd-network:x:102:104:systemd Network Management,,,:/run/systemd:/usr/sbin/nologin\n\
systemd-resolve:x:103:105:systemd Resolver,,,:/run/systemd:/usr/sbin/nologin\n\
sshd:x:104:65534::/run/sshd:/usr/sbin/nologin\n\
messagebus:x:105:107::/nonexistent:/usr/sbin/nologin\n\
ezid-user1:x:1001:1001::/home/user1:/bin/bash\n\
test-group-admin:x:60000:60000::/home/testgroupadmin:/bin/bash\n".strip()

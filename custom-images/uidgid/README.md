# UIDGID

## Overview

Manages UNIX user/group names and ids for JupyterHub based on alternate
identities provided by upstream systems like AD/ADX, Cognito, and Proper.
Supports POSIX file system behaviors used to implement file sharing between
team members where teams are associated with UNIX groups.  Interacts with the
JupyterHub spawner to automatically generate UNIX-compatible names and id
numbers which it tracks in Rosetta tables correlating to equivalent upstream
identities.   Also supplies the spawner with UNIX /etc/passwd and /etc/group
as strings which can be plugged into the notebook container replacing the defaults.

More discussion and diagrams (possibly dated) are here:

   https://innerspace.stsci.edu/pages/viewpage.action?pageId=463345388

## Design Components

There are effectively two top level aspects to the UIDGID design:

1. A Python library API which can be queried directly to create and initialize and/or
retrieve UNIX user identities.

2. A web service wrapper for the library enabling it to run in its own isolated container.

Both client and server are contained in a single UIDGID package. The JupyterHub
spawner running in the hub pod calls the UIDGID client interface in the UIDGID
package to interact with the microservice.   The UIDGID microservice server
runs in its own container with required file mounts and permissions.

A key point is that when the library is queried for a new user or group,
it will automatically create and configure the corresponding $HOME or team
directory.  While we originally just ran the hub container as root and embedded
the UIDGID library directly in it, this introduced the risk that compromising
the hub container could lead to abusing those root permissions arbitrarily.

Consequently we moved the library to a dedicated sidecar container and exposed
it via a web microservice. This enabled us to restore the hub container to
running as a normal user and hide more sensitive capabilities:

1. Linux capabilities required to perform arbitrary chown and chmod
2. Root permissions reduced well below CAP_SYS_ADMIN but still dangerous.
3. sudo and allPrivilegeEscalation: true needed to switch from the normal
   service user to root to execute chown only.
4. Broad write access to all of /users and /teams, effectively all user data.

Since the hub pod is configured so that pod-to-pod communications are private
(this is also a function of the containers and URLs they bind to) and the
microservice is only accessible in the hub pod, the attack surface avaialble to
compromise the sensitive features is greatly reduced,  nominally to REST calls
from the hub container two just entry points.

## Development

Sourcecode for the package is largely under the "uidgid" package directory
with the possible exception of pre-initialized/mock table data files.

Tests are under the directory "tests".

There is a Dockerfile which defines the sidecar container and runs the uidgid
microservice,  both for tests and for prodcution use on the hub.

There is a Makefile which supports several useful development functions:

1. `make test` -- run all the unit tests using pytest.   This includes running
                the supporting live-test script which runs the uidgid-service
                container as a Docker daemon and directly calls the entry points

2. `make lint` -- run flake8, bandit, mypy, black checks on the code.

    `lint/flake8` -- checks for PEP8 compliance and broader style issues.

    `lint/bandit` -- checks for security issues.

    `lint/mypy` -- checks for type annotation issues,  passing but work in progress.

    `lint/black` -- checks for whitespace issues and can update code to standardize.

3. `make build-and-push` -- builds and pushes the uidgid-service sidecar for use on the hub.

4. `make coverage`  -- runs unit tests in coverage mode generating HTML report

5. `make load-test`  -- runs basic service calls using locust to explore performance

## Debug Advice

### Unit Testing

The `make test` function is designed to break out into pdb and pause for input.  This
works well when uidgid is installed locally and pdb is connected directly to the
library code.  However,  when running through the client,  pdb may present directly
little more than "Code 500 Internal Server Error" while the server itself where the
problem occurred remains completely opaque.

There are two very useful approaches for addressing the problem of looking inside
the container:

1. While the test run is stuck in pdb,  you can switch to an alternate terminal
window to interact with Docker where the service container is still running.  In
this way it is possible to exec into the container to poke around and inspect
the file system.  Likewise it is possible to use `docker log` to dump the server
log while the container is still running.

2. After quitting pdb and allowing `make test` to shut down the service container
and test,  there is a file `live-test.log` which is left behind and contains
as much of the service log as was successfully output to Docker,  hopefully all of it.
The caveat is that normally the server log is a background system so there is
potential it might not make it out if the server completely crashes.

### On the Platform

In the current implementation the uidgid library is running as a service in a
sidecar container in the hub pod.   Because it is in sidecar,  the log output
of the server container is not in the hub log as it was when uidgid was a library
call entirely in the hub process and container.

To get uidgid log output on the platform:

```
klogs hub default uidgid-service
```

Use the `klogs` shell function to fetch the kubernetes log from the `uidgid-service`
container running in the `hub` pod of the `default` namespace.

To exec into the uidgid-service container:

```
kexec2 hub default uidgid-service
```

Use the `kexec2` shell function to open an interactive bash shell in the `uidgid-service`
container in the `hub` pod of the `default` namespace.

## Background

0. Presented with a user,  their active team, and the list of their known teams,
uidgid will perform lookups to determine the uid and gid for the user and group
as well as their human readable names for Linux.  Broadly,  the names and IDs
used by systems outside JupyterHub are not directly usable by Ubuntu-based
notebook containers.   Similarly,  the uid and gid values used by Ubuntu do not
exist in general outside JupyterHub,  so they are invented here as needed.

1. Always,  uidgid will return the contents of /etc/passwd and /etc/group files.
These can then be "plugged in" as strings by Kubernetes and the Spawner to
replace the stock files already in the container with versions which know about
hub-specific users and groups.  Anytime a user or group is created, modified, or
deactivated,  uidgid will first update the tables of users and groups, and then
generate /etc/passwd and /etc/group from the updated tables.

Uid's and Gid's are never deleted or re-assigned;  this enables identification
of files that belonged to past users which may e.g. still exist and be owned
by a team.

2. If a user identity is queried for the first time,  uidgid will create a
new Ubuntu user and personal-user-group, and assign their uid and gid the same
integer value.

3. If a team identity is queried for the first time,  uidgid will create a
new Ubuntu group representing the team,  a new Ubuntu pseudo-user named
<team>-admin to represent the group admin(s),  and assign both the gid and uid
the same integer value.   A shared directory with TBD appropriate permissions
and structure will also be created for the team.  The user will be added to
the new team group.

4. If an *existing* team identity is queried,  uidgid will still check that
the user is a member of the corresponding group,  and if not,  will add them.

5. When an existing user is queried,  their requested groups will be checked
against the list of groups they are/were already a member of.  If there is a
group which is no longer requested,  the user will be removed from the group.

6. Although the implementations are hidden in the user, group, and username
modules,  this function is the interface to the Spawner and basis for the
main entry point if a REST service is ever added.   A more advanced service
might later perform more granular REST operations on users and groups.

Note that this function call has no direct interface to the human user so
details like "which groups/roles are displayed to the user as options and/or
designated as active" falls to the spawner,  possibly generating a login
page dynamically to solicit appropriate additional information.

## Implicit relationships

Calling the function and reacting to the outputs both rely on understanding
some basic relationships which are maintained by uidgid:

1. The gid of a user's personal group is the same as the uid of the user.
2. The uid and gid of a team/group and their admin user are the same.
3. The username and their personal groupname are the same.
4. The groupname and its admin user are `<groupname>` and `<groupname>-admin`.
5. The teamname and the name of the team's admin user are `<teamname>` and `<teamname-admin>`.
6. An admin user has a normal `/home/<groupname>-admin` directory.
7. Requesting a new user will automatically request their personal group as well
   but it has no `/teams` directory.
8. Requesting a new team will automatically request the corresponding `-admin`
   user which does have a `$HOME` directory.

Leveraging these relationships should permit the spawner to choose an
appropriate user and group,  where group is a choice between the
user's personal group and their active team's group,  and user is a
choice between the spawner's requested user and a team admin user when
a user chooses to adopt an admin role which might be added as a simple check-box
on the spawn page.   The spawner would need to verify that the user has `-admin`
permissions for their selected group.

## Directory Creation

In addition to managing user names and ids with the Rosetta tables,
the uidgid library automatically allocates a home directory for each user
and a group directory for each team while carefully ascribing specific
ownership and permissions to each.   Most importantly,  the ownership of the home
directory is given to the user and their group,  and the ownership of
team directories are given to the team admin user while remaining
writable by all members. The need to both change file and directory
ownership and permissions arbitrarily requires elevated permissions which
are equivalent to root which resulted in the microservice architecture.

## UIDGID as a web service

Because creating directories with correct ownership and permissions requires
elevated permissions which are effectively root, merely calling the library
from code in the public hub container is not considered safe.  Instead, we
bundle up the UIDGID library as a web service running in a sidecar container
which can be called from the spawner.  While the sidecar still runs with
elevated permissions,  it is private,  and only accessible through tightly
controlled web calls.   This greatly reduces the attack surface,  and
additionally,  keeps writable mounts for /users and /teams private to the
sidecar vs. fully available in the public hub container which is more vulnerable
to compromise due to a public attack surface.

### Web service stack

Because the web service is a separate container based on a dedicated image, our
choice of software for the service expands beyond the hub's Tornado software to
whatever is easiest.   Along those lines,  we first noticed the simplicity of
Flask, and then slightly later quart which has an almost identical API
functionally while supporting async io and possessing very clear page 1 examples.

### Web service entry points

#### check-alive [GET]

This is just a simple health check to ensure the service is running.  It
requires no parameters and returns the JSON string "ok".

#### get-spawn-info [PUT]

This is the main entry point for the spawner to request information about
the user and group to be spawned.  This is a trivially thin wrapper around
the uidgid library's get_spawn_info function.  Calling it requires a JSON object
like this:

```
    data = dict(
        stsci_uuid=stsci_uuid,
        stsci_ezid=stsci_ezid,
        active_team=active_team,
        teams=teams,
    )
```

and it retuns a JSON object like this:

```
@dataclass
class SpawnInfo:
    """All of the values returned from the uid/gid system needed to spawn a user
    and fully identify them in the context of a notebook container and Ubuntu.
    """

    uid: Uid
    gid: Gid  # active group
    all_user_gids: list[Gid]  # all groups
    username: UserName
    groupname: GroupName  # active group
    etc_passwd: str
    etc_group: str
```

### Web client API and caching

For convenience, the `uidgid.client` module defines `check_alive` and
`get_spawn_info` functions which hide the underlying web requests and are
drop-in replacements for the library calls.  While the web service could be
called directly, it is more convenient to use the client API.

More recently, LRU caching has been introduced into the client API as the
function `cached_get_spawn_info` with a cache size of 1024.  This means that
when the same set of parameters is used twice, the second time the response
will be taken directly from the LRU cache and no other side effects will occur.
After 1024 distinct parameter sets have been recieved,  the cache will begin to
forget entries that were least recently used whenever new entries arrive. This
prevents uncontrolled growth of the cache.  NOTE that redploying JupyterHub will
also clear the cache resulting in a slow login for every user the first time
they use the hub.

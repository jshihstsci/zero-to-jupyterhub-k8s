These specs are used to run repeatable tests using the sh-doctest program found
at https://github.com/jaytmiller/sh-doctest:

$ pip install git+https://github.com/jaytmiller/sh-doctest

The purpose of the specs is to define and test expected behavior for our EFS
directory and permission scheme.  sh-doctest runs and verifies the specs.

The specs are intended to be run in two phases:

I. From the hub perspective as root to check out basic directory structure
and permissions / root ownership,  and to set up notebook testing by
populating the test-specs directory:

000-hdr-trlr
110-hub
120-nb-setup

$ python -m sh_doctest.main 000-hdr-trlr 110-hub
$ python -m sh_doctest.main 000-hdr-trlr 120-nb-setup


II. From the notebook user perspective to test expected capabilities
and prohibitions for a user:

000-hdr-trlr
010-basic-perms
040-team-member
050-no-access

$ python -m sh_doctest.main 000-hdr-trlr 010-basic-perms 040-team-member 050-no-access



NOTE:

Most of the specs are written as templates which enable replacing
tokens like <var> with values which are defined in an expansion
following the template.  Each template can be expanded with an
arbitrary number of variable sets.

Running these tests as a new tester or on a new system may require
changing the values of template variables appropriately,  e.g.
re-defining the various users, groups, and ids which play out
roles in the tests by redefining variables in the template
expansions.




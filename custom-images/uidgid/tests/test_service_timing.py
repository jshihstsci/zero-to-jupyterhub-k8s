"""Top level library module providing spawner a one-stop-shop i/f to uid/gid"""

from .test_service import test_add_new_user_and_group as add_new_user_and_group
from .test_service import (
    test_add_existing_user_to_new_group as add_existing_user_to_new_group,
)
from .test_service import test_everything_already_defined as everything_already_defined


def test_add_new_user_and_group_timing_svc(benchmark):
    benchmark(add_new_user_and_group)


def test_add_existing_user_to_new_group_timing_svc(benchmark):
    benchmark(add_existing_user_to_new_group)


def test_everything_already_defined_timing_svc(benchmark):
    benchmark(everything_already_defined)

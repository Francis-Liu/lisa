# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

import asyncio
import functools
from argparse import Namespace
from typing import Iterable, Optional, cast

from lisa import notifier
from lisa.parameter_parser.runbook import load_runbook
from lisa.runner import RootRunner
from lisa.testselector import select_testcases
from lisa.testsuite import TestCaseRuntimeData
from lisa.util import LisaException, constants
from lisa.util.logger import enable_console_timestamp, get_logger
from lisa.util.perf_timer import create_timer

_get_init_logger = functools.partial(get_logger, "init")


def run(args: Namespace) -> int:
    enable_console_timestamp()
    runbook = load_runbook(args.runbook, args.variables)

    if runbook.notifier:
        notifier.initialize(runbooks=runbook.notifier)
    run_message = notifier.TestRunMessage(
        test_project=runbook.test_project,
        test_pass=runbook.test_pass,
        run_name=constants.RUN_NAME,
        tags=runbook.tags,
    )
    notifier.notify(run_message)

    run_status = notifier.TestRunStatus.FAILED
    run_timer = create_timer()
    run_error_message = ""
    try:
        runner = RootRunner(runbook)
        asyncio.run(runner.start())
        run_status = notifier.TestRunStatus.SUCCESS
    except Exception as identifier:
        run_error_message = str(identifier)
        raise identifier
    finally:
        run_message = notifier.TestRunMessage(
            status=run_status, elapsed=run_timer.elapsed(), message=run_error_message
        )
        notifier.notify(run_message)
        notifier.finalize()

    return runner.exit_code


# check runbook
def check(args: Namespace) -> int:
    load_runbook(args.runbook, args.variables)
    return 0


def list_start(args: Namespace) -> int:
    runbook = load_runbook(args.runbook, args.variables)
    list_all = cast(Optional[bool], args.list_all)
    log = _get_init_logger("list")
    if args.type == constants.LIST_CASE:
        if list_all:
            cases: Iterable[TestCaseRuntimeData] = select_testcases()
        else:
            cases = select_testcases(runbook.testcase)
        for case_data in cases:
            log.info(
                f"case: {case_data.name}, suite: {case_data.metadata.suite.name}, "
                f"area: {case_data.suite.area}, "
                f"category: {case_data.suite.category}, "
                f"tags: {','.join(case_data.suite.tags)}, "
                f"priority: {case_data.priority}"
            )
    else:
        raise LisaException(f"unknown list type '{args.type}'")
    log.info("list information here")
    return 0

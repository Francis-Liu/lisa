# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

from typing import Any

from assertpy import assert_that

from lisa import Node, TestCaseMetadata, TestSuite, TestSuiteMetadata
from lisa.operating_system import Posix
from lisa.tools import Echo, Uname


@TestSuiteMetadata(
    area="demo",
    category="functional",
    description="""
    this is an example test suite.
    it helps to understand how to write a test case.
    """,
)
class HelloWorld(TestSuite):
    @TestCaseMetadata(
        description="""
        this test case use default node to
            1. get system info
            2. echo hello world!
        """,
        priority=0,
    )
    def hello(self, node: Node) -> None:
        if node.os.is_posix:
            assert isinstance(node.os, Posix)
            info = node.tools[Uname].get_linux_information()
            self.log.info(
                f"release: '{info.uname_version}', version: '{info.kernel_version}', "
                f"hardware: '{info.hardware_platform}', os: '{info.operating_system}'"
            )
        else:
            self.log.info("windows operating system")

        # get process output directly.
        echo = node.tools[Echo]
        hello_world = "hello world!"
        result = echo.run(hello_world)
        assert_that(result.stdout).is_equal_to(hello_world)
        assert_that(result.stderr).is_equal_to("")
        assert_that(result.exit_code).is_equal_to(0)

    @TestCaseMetadata(
        description="""
        demonstrate a simple way to run command in one line.
        """,
        priority=1,
    )
    def bye(self, node: Node) -> None:
        # use it once like this way before use short cut
        node.tools[Echo]
        assert_that(str(node.tools.echo("bye!"))).is_equal_to("bye!")

    def before_suite(self, **kwargs: Any) -> None:
        self.log.info("setup my test suite")
        self.log.info(f"see my code at {__file__}")

    def after_suite(self, **kwargs: Any) -> None:
        self.log.info("clean up my test suite")

    def before_case(self, **kwargs: Any) -> None:
        self.log.info("before test case")

    def after_case(self, **kwargs: Any) -> None:
        self.log.info("after test case")

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

import re
from typing import Any

from lisa.executable import Tool
from lisa.util import find_patterns_in_lines


class Waagent(Tool):
    __version_pattern = re.compile(r"(?<=\-)([^\s]+)")

    @property
    def command(self) -> str:
        return self._command

    def _check_exists(self) -> bool:
        return True

    def _initialize(self, *args: Any, **kwargs: Any) -> None:
        self._command = "waagent"

    def get_version(self) -> str:
        result = self.run("-version")
        if result.exit_code != 0:
            self._command = "/usr/sbin/waagent"
            result = self.run("-version")
        # When the default command python points to python2,
        # we need specify python3 clearly.
        # e.g. bt-americas-inc diamondip-sapphire-v5 v5-9 9.0.53.
        if result.exit_code != 0:
            self._command = "python3 /usr/sbin/waagent"
            result = self.run("-version")
        found_version = find_patterns_in_lines(result.stdout, [self.__version_pattern])
        return found_version[0][0] if found_version[0] else ""


class VmGeneration(Tool):
    """
    This is a virtual tool to detect VM generation of Hyper-V technology.
    """

    @property
    def command(self) -> str:
        return "ls -lt /sys/firmware/efi"

    def _check_exists(self) -> bool:
        return True

    def get_generation(self) -> str:
        cmd_result = self.run()
        if cmd_result.exit_code == 0:
            generation = "2"
        else:
            generation = "1"
        return generation

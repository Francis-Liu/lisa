# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

import re
from enum import Enum
from typing import Any, cast

from lisa.feature import Feature
from lisa.operating_system import Linux, Redhat, Ubuntu
from lisa.tools import Uname
from lisa.util import LisaException

FEATURE_NAME_GPU = "Gpu"

ComputeSDK = Enum(
    "ComputeSDK",
    [
        # GRID Driver
        "GRID",
        # CUDA Driver
        "CUDA",
    ],
)

# Link to the latest GRID driver
# The DIR link is
# https://download.microsoft.com/download/9/5/c/95c667ff-ab95-4c56-89e0-e13e9a76782d/NVIDIA-Linux-x86_64-460.32.03-grid-azure.run
GRID_DRIVER = "https://go.microsoft.com/fwlink/?linkid=874272"


class Gpu(Feature):
    def __init__(self, node: Any, platform: Any) -> None:
        super().__init__(node, platform)
        self._log = self._node.log

    @classmethod
    def name(cls) -> str:
        return FEATURE_NAME_GPU

    # download and install NVIDIA grid driver
    def _install_grid_driver(self, version: str) -> None:
        self._log.info("Starting GRID driver installation")
        if not version.strip():
            version = GRID_DRIVER

        # grid_filename = "NVIDIA-Linux-x86_64-grid.run"

        # download and install the NVIDIA GRID driver

    # download and install CUDA Driver
    def _install_cuda_driver(self, version: str) -> None:
        self._log.info("Starting CUDA driver installation")
        cuda_repo = ""
        linux_os: Linux = cast(Linux, self._node.os)

        if not version.strip():
            version = "10.1.105-1"

        # CUDA driver installation for redhat distros
        if isinstance(self._node.os, Redhat):
            cuda_repo_pkg = f"cuda-repo-rhel7-{version}.x86_64.rpm"
            cuda_repo = (
                "http://developer.download.nvidia.com/"
                f"compute/cuda/repos/rhel7/x86_64/{cuda_repo_pkg}"
            )
            linux_os = Redhat(self._node)

        # CUDA driver installation for Ubuntu distros
        elif isinstance(self._node.os, Ubuntu):
            release_version = self._node.os._os_version.release
            release = re.sub("[^0-9]+", "", release_version)
            cuda_repo_pkg = f"cuda-repo-ubuntu{release}_{version}_amd64.deb"
            cuda_repo = (
                "http://developer.download.nvidia.com/compute/"
                f"cuda/repos/ubuntu{release}/x86_64/{cuda_repo_pkg}"
            )
            linux_os = Ubuntu(self._node)

        else:
            raise LisaException(
                f"Distro {self._node.os.__class__.__name__}"
                "not supported to install CUDA driver."
            )

        # download and install the cuda driver package from the repo
        linux_os.install_packages(f"{cuda_repo}", signed=False)

    def install_gpu_dep(self) -> None:
        uname_tool = self._node.tools[Uname]
        uname_ver = uname_tool.get_linux_information().uname_version

        # install dependency libraries for redhat and CentOS
        if isinstance(self._node.os, Redhat):
            # install the kernel-devel and kernel-header packages
            package_name = f"kernel-devel-{uname_ver} kernel-headers-{uname_ver}"
            self._node.os.install_packages(package_name)

            # mesa-libEGL install/update is require to avoid a conflict between
            # libraries - bugzilla.redhat 1584740
            package_name = "mesa-libGL mesa-libEGL libglvnd-devel"
            self._node.os.install_packages(package_name)

            # install dkms
            package_name = "dkms"
            self._node.os.install_packages(package_name, signed=False)

        # install dependency libraraies for Ubuntu
        elif isinstance(self._node.os, Ubuntu):
            package_name = (
                f"build-essential libelf-dev linux-tools-{uname_ver}"
                f" linux-cloud-tools-{uname_ver} python libglvnd-dev ubuntu-desktop"
            )
            self._node.os.install_packages(package_name)

    def install_compute_sdk(self, driver: ComputeSDK, version: str = "") -> None:
        if driver == ComputeSDK.GRID:
            self._install_grid_driver(version)
        elif driver == ComputeSDK.CUDA:
            self._install_cuda_driver(version)
        else:
            raise LisaException("No valid driver SDK name provided to install.")

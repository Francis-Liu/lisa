# Install LISA

- [Install LISA](#install-lisa)
  - [Prerequisites](#prerequisites)
  - [Install Python](#install-python)
    - [Windows](#windows)
    - [Linux](#linux)
  - [Install dependencies](#install-dependencies)
  - [Clone code](#clone-code)
  - [Install Poetry and Python dependencies](#install-poetry-and-python-dependencies)
    - [Install Poetry in Linux](#install-poetry-in-linux)
    - [Install Poetry in Windows](#install-poetry-in-windows)
  - [FAQ and Troubleshooting](#faq-and-troubleshooting)

LISA can be installed on any computer without having to be installed on each
tested node. It can be installed on tested nodes to perform local testing. It
can connect to another tested node using SSH. The following are examples showing
where LISA is installed.

![deploy](img/deploy.svg)

LISA supports to run on Windows and Linux. Follow below steps to install LISA
from source code.

## Prerequisites

LISA needs to be installed on a computer that can access the computer to be
tested. For tested computers, LISA is not required to be installed. The computer
under test can be a local computer.

- Can access the tested platform, like Azure, Hyper-V, or else. It recommends
  having good bandwidth and low network latency.
- At least 2 CPU cores and 4GB memory.

## Install Python

Lisa is tested on [Python 3.8 64 bits](https://www.python.org/). If there are
Python installed already, please make sure effective Python's version is 3.8
64-bit or above.

LISA is developed and tested with Python 3.8 (64 bit). The latest version of
Python 3.8 is recommended. If LISA is not compatible with higher Python version,
[file an issue](https://github.com/microsoft/lisa/issues/new) to us.

### Windows

Navigate to [Python releases for
Windows](https://www.python.org/downloads/windows/). Download and install
*Windows installer (64-bit)* from latest Python 3.8 64-bits or higher version.

### Linux

For some Linux distributions, you can install latest Python 3.8 (64-bit) by its
guidance, or build from source code. Below is how to install in Ubuntu.

```bash
sudo apt update
sudo apt install software-properties-common -y
sudo add-apt-repository ppa:deadsnakes/ppa -y
sudo apt install python3.8 python3.8-dev -y
```

## Install dependencies

Since LISA is installed from source, `git` is necessary. And some packages need
to be built, so the build tools are also needed.

In Linux, it needs `git`, `gcc`, and other Azure dependencies. Below is depended
packages on Ubuntu.

```bash
sudo apt install git gcc libgirepository1.0-dev libcairo2-dev virtualenv -y
```

In Windows, you need to install [git](https://git-scm.com/downloads) and [Visual
C++ redistributable package](https://aka.ms/vs/16/release/vc_redist.x64.exe)

## Clone code

Open a terminal window, and enter the folder, which uses to put LISA code. If
you want to use the latest version, checkout the main branch.

```sh
git clone https://github.com/microsoft/lisa.git
cd lisa
```

## Install Poetry and Python dependencies

Poetry is used to manage Python dependencies of LISA. Execute corresponding
script to install Poetry.

Note, it's important to enter LISA's folder to run below command, since Poetry
manages dependencies by the working folder.

### Install Poetry in Linux

```bash
curl -sSL https://raw.githubusercontent.com/python-poetry/poetry/master/install-poetry.py | python3 -
source ../.profile
poetry install
```

### Install Poetry in Windows

Enter the PowerShell command prompt and execute,

```powershell
(Invoke-WebRequest -Uri https://raw.githubusercontent.com/python-poetry/poetry/master/install-poetry.py -UseBasicParsing).Content | python -
# Add to PATH Poetry's binary location (either this or via Window's global env. vars. menu):
$env:PATH += ";$env:APPDATA\Python\Scripts"
poetry install
```

## FAQ and Troubleshooting

Refer to [FAQ and troubleshooting](troubleshooting.md).

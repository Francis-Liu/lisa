# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Tuple,
    Type,
    Union,
)

from retry.api import retry_call

from lisa import notifier, schema, search_space
from lisa.environment import EnvironmentSpace, EnvironmentStatus
from lisa.feature import Feature
from lisa.operating_system import OperatingSystem
from lisa.util import (
    LisaException,
    NotRunException,
    PassedException,
    SkippedException,
    constants,
    get_datetime_path,
    set_filtered_fields,
)
from lisa.util.logger import Logger, get_logger
from lisa.util.perf_timer import Timer, create_timer

if TYPE_CHECKING:
    from lisa.environment import Environment


TestStatus = Enum(
    "TestStatus", ["NOTRUN", "RUNNING", "FAILED", "PASSED", "SKIPPED", "ATTEMPTED"]
)

_all_suites: Dict[str, TestSuiteMetadata] = dict()
_all_cases: Dict[str, TestCaseMetadata] = dict()


@dataclass
class TestResultMessage(notifier.MessageBase):
    # id is used to identify the unique test result
    id_: str = ""
    type: str = "TestResult"
    name: str = ""
    status: TestStatus = TestStatus.NOTRUN
    message: str = ""
    information: Dict[str, str] = field(default_factory=dict)


@dataclass
class TestResult:
    # id is used to identify the unique test result
    id_: str
    runtime_data: TestCaseRuntimeData
    status: TestStatus = TestStatus.NOTRUN
    elapsed: float = 0
    message: str = ""
    environment: Optional[Environment] = None
    check_results: Optional[search_space.ResultReason] = None
    information: Dict[str, Any] = field(default_factory=dict)

    @property
    def can_run(self) -> bool:
        return self.status == TestStatus.NOTRUN

    def __post_init__(self, *args: Any, **kwargs: Any) -> None:
        self._send_result_message()
        self._timer: Timer

    @property
    def name(self) -> str:
        return self.runtime_data.metadata.name

    def handle_exception(
        self, exception: Exception, log: Logger, phase: str = ""
    ) -> None:
        if phase:
            phase = f"{phase} "
        if isinstance(exception, SkippedException):
            log.info(f"case skipped: {exception}")
            log.debug("case skipped", exc_info=exception)
            # case is skipped dynamically
            self.set_status(TestStatus.SKIPPED, f"{phase}skipped: {exception}")
        elif isinstance(exception, NotRunException):
            log.info(f"case keep NOTRUN: {exception}")
            log.debug("case NOTRUN", exc_info=exception)
            # case is not run dynamically.
            self.set_status(TestStatus.NOTRUN, f"{phase}notrun: {exception}")
        elif isinstance(exception, PassedException):
            log.info(f"case passed with warning: {exception}")
            log.debug("case passed with warning", exc_info=exception)
            # case can be passed with a warning.
            self.set_status(TestStatus.PASSED, f"{phase}warning: {exception}")
        else:
            if self.runtime_data.ignore_failure:
                log.info(f"case failed and ignored: {exception}")
                self.set_status(TestStatus.ATTEMPTED, f"{phase}{exception}")
            else:
                log.error("case failed", exc_info=exception)
                self.set_status(TestStatus.FAILED, f"{phase}failed: {exception}")

    def set_status(
        self, new_status: TestStatus, message: Union[str, List[str]]
    ) -> None:
        if message:
            if isinstance(message, str):
                message = [message]
            if self.message:
                message.insert(0, self.message)
            self.message = "\n".join(message)
        if self.status != new_status:
            self.status = new_status
            if new_status == TestStatus.RUNNING:
                self._timer = create_timer()
            self._send_result_message()

    def check_environment(
        self, environment: Environment, save_reason: bool = False
    ) -> bool:
        requirement = self.runtime_data.metadata.requirement
        assert requirement.environment
        check_result = requirement.environment.check(environment.capability)
        if (
            check_result.result
            and requirement.os_type
            and environment.status == EnvironmentStatus.Connected
        ):
            for node in environment.nodes.list():
                # use __mro__ to match any super types.
                # for example, Ubuntu satisfies Linux
                node_os_capability = search_space.SetSpace[Type[OperatingSystem]](
                    is_allow_set=True, items=type(node.os).__mro__
                )
                check_result.merge(
                    requirement.os_type.check(node_os_capability), "os_type"
                )
                if not check_result.result:
                    break
        if save_reason:
            if self.check_results:
                self.check_results.merge(check_result)
            else:
                self.check_results = check_result
        return check_result.result

    def _send_result_message(self) -> None:
        if hasattr(self, "_timer"):
            self.elapsed = self._timer.elapsed(False)

        fields = ["status", "elapsed", "id_"]
        result_message = TestResultMessage()
        set_filtered_fields(self, result_message, fields=fields)

        # get information of default node, and send to notifier.
        if self.environment:
            self.information.update(self.environment.get_information())
        result_message.information.update(self.information)
        result_message.message = self.message[0:2048] if self.message else ""
        result_message.name = self.runtime_data.metadata.full_name
        notifier.notify(result_message)


@dataclass
class TestCaseRequirement:
    environment: Optional[EnvironmentSpace] = None
    environment_status: EnvironmentStatus = EnvironmentStatus.Connected
    platform_type: Optional[search_space.SetSpace[str]] = None
    os_type: Optional[search_space.SetSpace[Type[OperatingSystem]]] = None

    def __post_init__(self, *args: Any, **kwargs: Any) -> None:
        if self.environment_status == EnvironmentStatus.Deployed and self.os_type:
            raise LisaException(
                "requirement doesn't support os_type, when status is Deployed"
            )


def simple_requirement(
    min_count: int = 1,
    min_nic_count: int = 1,
    node: Optional[schema.NodeSpace] = None,
    supported_platform_type: Optional[List[str]] = None,
    unsupported_platform_type: Optional[List[str]] = None,
    supported_os: Optional[List[Type[OperatingSystem]]] = None,
    unsupported_os: Optional[List[Type[OperatingSystem]]] = None,
    supported_features: Optional[List[Type[Feature]]] = None,
    unsupported_features: Optional[List[Type[Feature]]] = None,
    environment_status: EnvironmentStatus = EnvironmentStatus.Connected,
) -> TestCaseRequirement:
    """
    define a simple requirement to support most test cases.
    """
    if node is None:
        node = schema.NodeSpace()

    node.node_count = search_space.IntRange(min=min_count)
    node.nic_count = search_space.IntRange(min=min_nic_count)
    if supported_features:
        node.features = search_space.SetSpace[str](
            is_allow_set=True,
            items=[x.name() for x in supported_features],
        )
    if unsupported_features:
        node.excluded_features = search_space.SetSpace[str](
            is_allow_set=False,
            items=[x.name() for x in unsupported_features],
        )
    nodes: List[schema.NodeSpace] = [node]

    platform_types = search_space.create_set_space(
        supported_platform_type, unsupported_platform_type, "platform type"
    )

    os = search_space.create_set_space(supported_os, unsupported_os, "operating system")

    return TestCaseRequirement(
        environment=EnvironmentSpace(nodes=nodes),
        platform_type=platform_types,
        os_type=os,
        environment_status=environment_status,
    )


DEFAULT_REQUIREMENT = simple_requirement()


class TestSuiteMetadata:
    def __init__(
        self,
        area: str,
        category: str,
        description: str,
        tags: Optional[List[str]] = None,
        name: str = "",
        requirement: TestCaseRequirement = DEFAULT_REQUIREMENT,
    ) -> None:
        self.name = name
        self.cases: List[TestCaseMetadata] = []
        self.tags: List[str] = tags if tags else []

        self.area = area
        self.category = category
        if tags:
            self.tags = tags
        else:
            self.tags = []
        self.description = description
        self.requirement = requirement

    def __call__(self, test_class: Type[TestSuite]) -> Callable[..., object]:
        self.test_class = test_class
        if not self.name:
            self.name = test_class.__name__
        _add_suite_metadata(self)

        @wraps(self.test_class)
        def wrapper(
            test_class: Type[TestSuite],
            metadata: TestSuiteMetadata,
        ) -> TestSuite:
            return test_class(metadata)

        return wrapper


class TestCaseMetadata:
    def __init__(
        self,
        description: str,
        priority: int = 2,
        requirement: Optional[TestCaseRequirement] = None,
    ) -> None:
        self.suite: TestSuiteMetadata

        self.priority = priority
        self.description = description
        if requirement:
            self.requirement = requirement

    def __getattr__(self, key: str) -> Any:
        # return attributes of test suite, if it's not redefined in case level
        assert self.suite, "suite is not set before use metadata"
        return getattr(self.suite, key)

    def __call__(self, func: Callable[..., None]) -> Callable[..., None]:
        self.name = func.__name__
        self.full_name = func.__qualname__

        self._func = func
        _add_case_metadata(self)

        @wraps(self._func)
        def wrapper(*args: Any, **kwargs: Any) -> None:
            parameters: Dict[str, Any] = dict()
            for name in kwargs.keys():
                if name in func.__annotations__:
                    parameters[name] = kwargs[name]
            func(*args, **parameters)

        return wrapper


class TestCaseRuntimeData:
    def __init__(self, metadata: TestCaseMetadata):
        self.metadata = metadata

        # all runtime setting fields
        self.select_action: str = ""
        self.times: int = 1
        self.retry: int = 0
        self.use_new_environment: bool = False
        self.ignore_failure: bool = False
        self.environment_name: str = ""

    def __getattr__(self, key: str) -> Any:
        # return attributes of metadata for convenient
        assert self.metadata
        return getattr(self.metadata, key)

    def clone(self) -> TestCaseRuntimeData:
        cloned = TestCaseRuntimeData(self.metadata)
        fields = [
            constants.TESTCASE_SELECT_ACTION,
            constants.TESTCASE_TIMES,
            constants.TESTCASE_RETRY,
            constants.TESTCASE_USE_NEW_ENVIRONMENT,
            constants.TESTCASE_IGNORE_FAILURE,
            constants.ENVIRONMENT,
        ]
        set_filtered_fields(self, cloned, fields)
        return cloned


class TestSuite:
    def __init__(
        self,
        metadata: TestSuiteMetadata,
    ) -> None:
        super().__init__()
        self._metadata = metadata
        self._should_stop = False
        self.log = get_logger("suite", metadata.name)

    def before_suite(self, **kwargs: Any) -> None:
        ...

    def after_suite(self, **kwargs: Any) -> None:
        ...

    def before_case(self, **kwargs: Any) -> None:
        ...

    def after_case(self, **kwargs: Any) -> None:
        ...

    def _create_case_log_path(self, case_name: str) -> Path:
        while True:
            path_name = f"{get_datetime_path()}-{case_name}"
            path = constants.RUN_LOCAL_PATH.joinpath(path_name)
            if not path.exists():
                break
        path.mkdir()
        return path

    def start(
        self,
        environment: Environment,
        # test cases to run, must be a test method in this class.
        case_results: List[TestResult],
    ) -> None:
        suite_error_message = ""

        # set the environment is not new, when it's used by any suite.
        environment.is_new = False
        test_kwargs = {
            "environment": environment,
            "node": environment.default_node,
        }

        #  replace to case's logger temporarily
        suite_log = self.log
        is_suite_continue, suite_error_message = self.__suite_method(
            self.before_suite, test_kwargs=test_kwargs, log=suite_log
        )

        for case_result in case_results:
            case_name = case_result.runtime_data.name

            case_result.environment = environment
            case_log = get_logger("case", f"{case_result.runtime_data.full_name}")

            case_kwargs = test_kwargs.copy()
            case_kwargs.update({"case_name": case_name})

            case_log.info(
                f"test case '{case_result.runtime_data.full_name}' is running"
            )
            is_continue: bool = is_suite_continue
            total_timer = create_timer()
            case_result.set_status(TestStatus.RUNNING, "")

            if is_continue:
                is_continue = self.__before_case(
                    case_result, test_kwargs=case_kwargs, log=case_log
                )
            else:
                case_result.set_status(TestStatus.SKIPPED, suite_error_message)

            if is_continue:
                self.__run_case(
                    case_result=case_result, test_kwargs=case_kwargs, log=case_log
                )

            self.__after_case(case_result, test_kwargs=case_kwargs, log=case_log)

            case_log.info(
                f"result: {case_result.status.name}, " f"elapsed: {total_timer}"
            )

            if self._should_stop:
                suite_log.info("received stop message, stop run")
                break

        self.__suite_method(self.after_suite, test_kwargs=test_kwargs, log=suite_log)

    def stop(self) -> None:
        self._should_stop = True

    def __suite_method(
        self, method: Callable[..., Any], test_kwargs: Dict[str, Any], log: Logger
    ) -> Tuple[bool, str]:
        result: bool = True
        message: str = ""
        timer = create_timer()
        method_name = method.__name__
        try:
            # use retry to pass dynamic parameters
            method(**test_kwargs)
        except Exception as identifier:
            result = False
            message = f"{method_name}: {identifier}"
        log.debug(f"{method_name} end in {timer}")
        return result, message

    def __before_case(
        self, case_result: TestResult, test_kwargs: Dict[str, Any], log: Logger
    ) -> bool:
        result: bool = True

        timer = create_timer()
        try:
            retry_call(
                self.before_case,
                fkwargs=test_kwargs,
                exceptions=Exception,
                tries=case_result.runtime_data.retry + 1,
                logger=log,
            )
        except Exception as identifier:
            log.error("before_case: ", exc_info=identifier)
            case_result.set_status(TestStatus.SKIPPED, f"before_case: {identifier}")
            result = False
        log.debug(f"before_case end in {timer}")

        return result

    def __after_case(
        self, case_result: TestResult, test_kwargs: Dict[str, Any], log: Logger
    ) -> None:
        timer = create_timer()
        try:
            retry_call(
                self.after_case,
                fkwargs=test_kwargs,
                exceptions=Exception,
                tries=case_result.runtime_data.retry + 1,
                logger=log,
            )
        except Exception as identifier:
            # after case doesn't impact test case result.
            log.error("after_case failed", exc_info=identifier)
        log.debug(f"after_case end in {timer}")

    def __run_case(
        self, case_result: TestResult, test_kwargs: Dict[str, Any], log: Logger
    ) -> None:
        timer = create_timer()
        case_name = case_result.runtime_data.name
        test_method = getattr(self, case_name)

        try:
            retry_call(
                test_method,
                fkwargs=test_kwargs,
                exceptions=Exception,
                tries=case_result.runtime_data.retry + 1,
                logger=log,
            )
            case_result.set_status(TestStatus.PASSED, "")
        except Exception as identifier:
            case_result.handle_exception(exception=identifier, log=log)
        log.debug(f"case end in {timer}")


def get_suites_metadata() -> Dict[str, TestSuiteMetadata]:
    return _all_suites


def get_cases_metadata() -> Dict[str, TestCaseMetadata]:
    return _all_cases


def _add_suite_metadata(metadata: TestSuiteMetadata) -> None:
    if metadata.name:
        key = metadata.name
    else:
        key = metadata.test_class.__name__
    exist_metadata = _all_suites.get(key)
    if exist_metadata is None:
        _all_suites[key] = metadata
    else:
        raise LisaException(
            f"duplicate test class name: {key}, "
            f"new: [{metadata}], exists: [{exist_metadata}]"
        )

    class_prefix = f"{key}."
    for test_case in _all_cases.values():
        if test_case.full_name.startswith(class_prefix):
            _add_case_to_suite(metadata, test_case)
    log = get_logger("init", "test")
    log.info(
        f"registered test suite '{key}' "
        f"with test cases: '{', '.join([case.name for case in metadata.cases])}'"
    )


def _add_case_metadata(metadata: TestCaseMetadata) -> None:

    full_name = metadata.full_name
    if _all_cases.get(full_name) is None:
        _all_cases[full_name] = metadata
    else:
        raise LisaException(f"duplicate test class name: {full_name}")

    # this should be None in current observation.
    # the methods are loaded prior to test class
    # in case logic is changed, so keep this logic
    #   to make two collection consistent.
    class_name = full_name.split(".")[0]
    test_suite = _all_suites.get(class_name)
    if test_suite:
        log = get_logger("init", "test")
        log.debug(f"add case '{metadata.name}' to suite '{test_suite.name}'")
        _add_case_to_suite(test_suite, metadata)


def _add_case_to_suite(
    test_suite: TestSuiteMetadata, test_case: TestCaseMetadata
) -> None:
    test_case.suite = test_suite
    test_suite.cases.append(test_case)

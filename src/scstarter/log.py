import logging
import logging.config
import uuid
from collections.abc import Callable
from typing import Generic, TypeVar

import structlog
from structlog.types import EventDict, WrappedLogger


class ConfigurationError(Exception):
    def __init__(self, message: str):
        super().__init__(message)


TProcessorResult = TypeVar("TProcessorResult")
TChainResult = TypeVar("TChainResult")

LogProcessor = Callable[[WrappedLogger, str, EventDict], TProcessorResult]


class ProcessorChain[TProcessorResult, TChainResult]:
    def __init__(self, final_processor: LogProcessor[TChainResult]):
        if not callable(final_processor):
            raise ConfigurationError(
                "Final processor must be a callable that accepts logger, name, event_dict"
            )
        self._pre_processors: list[LogProcessor[TProcessorResult]] = []
        self._processors: list[LogProcessor[TProcessorResult]] = []
        self._final_processor = final_processor


class ProcessorChainBuilder:
    def __init__(self):
        self._processors = {}

    # def with_contextvars(self):
    #     self._processors.update(
    #         {"merge_contextvars": structlog.contextvars.merge_contextvars}
    #     )
    #     return self

    # def with_log_level(self):
    #     self._processors.update(
    #         {"log_level": structlog.stdlib.add_log_level}
    #     )
    #     return self

    # def with_logger_name(self):
    #     self._processors.update(
    #         {"logger_name": structlog.stdlib.add_logger_name}
    #     )
    #     return self

    # def with_time_stamper(self, fmt="iso", utc: bool = True, key="timestamp"):
    #     self._processors.update(
    #         {"timestamp": structlog.processors.TimeStamper(fmt=fmt, utc=utc, key=key)}
    #     )
    #     return self


chain = ProcessorChain[EventDict, str | bytes](structlog.processors.JSONRenderer())

#######################################################################################
#######################################################################################


shared_processor_chain = [
    structlog.contextvars.merge_contextvars,
    structlog.stdlib.add_log_level,
    structlog.stdlib.add_logger_name,
    structlog.processors.TimeStamper(fmt="iso"),
]

processor_chain = {
    "logging": shared_processor_chain
    + [
        structlog.stdlib.ExtraAdder(),
    ],
    "structlog": shared_processor_chain
    + [
        structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
    ],
    "main": [
        structlog.stdlib.ProcessorFormatter.remove_processors_meta,
        structlog.processors.JSONRenderer(),
    ],
}

structlog.configure(
    processors=processor_chain["structlog"],
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logging.config.dictConfig(
    {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "structlog": {
                "()": structlog.stdlib.ProcessorFormatter,
                "foreign_pre_chain": processor_chain["logging"],
                "processors": processor_chain["main"],
            }
        },
        "handlers": {
            "default": {
                "level": "DEBUG",
                "class": "logging.StreamHandler",
                "formatter": "structlog",
            }
        },
        "loggers": {
            "com.kreigan.scstarter.log": {
                "handlers": ["default"],
                "level": "DEBUG",
                "propagate": False,
            }
        },
        "root": {
            "handlers": ["default"],
            "level": "DEBUG",
        },
    }
)

trace_id = str(uuid.uuid4())

structlog.contextvars.clear_contextvars()
structlog.contextvars.bind_contextvars(trace_id=trace_id)

standard_logger = logging.getLogger("com.kreigan.scstarter.log")
struct_logger = structlog.get_logger("com.kreigan.scstarter.log")
sql_logger = logging.getLogger("sqlalchemy.engine")

standard_logger.info("Hello, Standard World!")
struct_logger.info("Hello, Structured World!")

standard_logger.debug("Hello, Standard World!")
struct_logger.debug("Hello, Structured World!")

sql_logger.info("Hello, SQL World!")

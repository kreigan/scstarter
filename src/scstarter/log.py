from collections.abc import Callable
from dataclasses import dataclass
from logging import Logger
from typing import Generic, Self, TypeVar

import structlog
from structlog.types import EventDict, WrappedLogger

from scstarter.exception import ConfigurationError


ChainOutput = str | bytes | bytearray
ProcessorOutput = EventDict | ChainOutput

TLogger = TypeVar("TLogger", bound=WrappedLogger)
TChainOutput = TypeVar("TChainOutput", bound=ChainOutput)
TProcessorInput = TypeVar("TProcessorInput", bound=ProcessorOutput)
TProcessorOutput = TypeVar("TProcessorOutput", bound=ProcessorOutput)

Processor = Callable[[TLogger, str, TProcessorInput], TProcessorOutput]

IntermediateProcessor = Processor[TLogger, TProcessorInput, TProcessorInput]
FinishingProcessor = Processor[TLogger, TProcessorInput, TChainOutput]


@dataclass
class ProcessorChain(Generic[TLogger, TProcessorInput, TChainOutput]):
    processors: list[IntermediateProcessor[TLogger, TProcessorInput]]
    output_processor: FinishingProcessor[TLogger, TProcessorInput, TChainOutput]


class ProcessorChainBuilder(Generic[TLogger, TProcessorInput, TChainOutput]):
    def __init__(
        self,
        output_processor: FinishingProcessor[TLogger, TProcessorInput, TChainOutput],
    ) -> None:
        self._pre_processors: list[IntermediateProcessor[TLogger, TProcessorInput]] = []
        self._processors: list[IntermediateProcessor[TLogger, TProcessorInput]] = []
        self._output_processor: FinishingProcessor[TLogger, TProcessorInput, TChainOutput] = output_processor

    def build(self) -> ProcessorChain[TLogger, TProcessorInput, TChainOutput]:
        return ProcessorChain(
            processors=self._pre_processors + self._processors,
            output_processor=self._output_processor,
        )


class StructurredLoggingChainBuilder(ProcessorChainBuilder[Logger, EventDict, TChainOutput]):
    def with_contextvars(self) -> Self:
        """
        Merges in global (context-local) context variables into every logger call.
        Adds contextvars to the beginning of the logger processor chain.

        Raises:
            ConfigurationError: If contextvars have already been added.

        Returns:
            self: The builder instance with contextvars added.
        """
        if self._has_context:
            raise ConfigurationError("Contextvars already added")
        self._pre_processors.insert(0, structlog.contextvars.merge_contextvars)
        return self

    def with_log_level(self) -> Self:
        self._processors.append(structlog.stdlib.add_log_level)
        return self

    def with_logger_name(self) -> Self:
        self._processors.append(structlog.stdlib.add_logger_name)
        return self

    def with_time_stamp(self, fmt: str = "iso", utc: bool = True, key: str = "timestamp") -> Self:
        self._processors.append(structlog.processors.TimeStamper(fmt=fmt, utc=utc, key=key))
        return self

    @property
    def _has_context(self) -> bool:
        return any(processor == structlog.contextvars.merge_contextvars for processor in self._pre_processors)


cb = StructurredLoggingChainBuilder(structlog.processors.KeyValueRenderer())

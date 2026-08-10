from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Generic, TypeVar, Union

T = TypeVar("T")
E = TypeVar("E")


@dataclass(frozen=True)
class Ok(Generic[T]):
    value: T


@dataclass(frozen=True)
class Err(Generic[E]):
    error: E


Result = Union[Ok[T], Err[E]]


def is_ok(result: Result[Any, Any]) -> bool:
    return isinstance(result, Ok)


def is_err(result: Result[Any, Any]) -> bool:
    return isinstance(result, Err)

"""Collision-resistant row ids (cuid2)."""

from cuid2 import Cuid

_generator = Cuid(length=24)


def new_id() -> str:
    return _generator.generate()

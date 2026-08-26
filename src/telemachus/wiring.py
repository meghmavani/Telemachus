"""Composition root — builds wired subsystems from configuration.

Both the ``start`` and ``chat`` entry points need the same objects
assembled the same way: a connected memory store, and a pipeline that
writes into it. Before this module existed each call site constructed
them independently, drifted from the real constructor signatures, and
raised ``TypeError`` at startup without any test noticing.

Construction lives here so that there is exactly one place where the
wiring can be wrong, and one place to test.
"""

from __future__ import annotations

import logging

from telemachus.config import TelemachusConfig
from telemachus.memory.store import MemoryStore
from telemachus.pipeline import CognitivePipeline
from telemachus.runtime.lifecycle import RuntimeLifecycle
from telemachus.runtime.state_store import RuntimeStateStore

logger = logging.getLogger("telemachus.wiring")


def build_memory_store(config: TelemachusConfig) -> MemoryStore:
    """Open and initialize the memory store described by ``config``.

    The returned store is connected and has its schema applied, so callers
    can use it immediately.

    Args:
        config: The system configuration.

    Returns:
        A connected MemoryStore.
    """
    db_path = config.paths.data_dir / config.database.path
    store = MemoryStore(db_path)
    store.connect()
    store.initialize_schema()
    logger.debug("Memory store ready at %s", db_path)
    return store


def build_pipeline(
    config: TelemachusConfig, memory_store: MemoryStore | None = None
) -> CognitivePipeline:
    """Build a cognitive pipeline backed by the configured memory store.

    Args:
        config: The system configuration.
        memory_store: An already-connected store. Built from config if None.

    Returns:
        A CognitivePipeline ready to process input.
    """
    store = memory_store if memory_store is not None else build_memory_store(config)
    return CognitivePipeline(memory_store=store)


def build_runtime(config: TelemachusConfig) -> RuntimeLifecycle:
    """Build a Runtime lifecycle ready to start.

    This is the composition root's only construction path for the
    Runtime: the state store it will connect to runtime.db, and the
    factory it will call to obtain the connected Core memory store, are
    both assembled here rather than inside ``RuntimeLifecycle`` itself —
    consistent with ``build_memory_store`` and ``build_pipeline`` above,
    and with the Runtime's role of coordinating Core components rather
    than constructing them independently.

    Args:
        config: The system configuration.

    Returns:
        A RuntimeLifecycle ready for ``start()``. Neither runtime.db nor
        telemachus.db is touched until then.
    """
    state_store = RuntimeStateStore(config.paths.data_dir / "runtime.db")
    return RuntimeLifecycle(
        config=config,
        state_store=state_store,
        memory_store_factory=lambda: build_memory_store(config),
    )

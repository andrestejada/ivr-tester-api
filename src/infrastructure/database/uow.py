"""Unit of Work for async database operations."""

from __future__ import annotations

from typing import Callable

from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.repositories.execution_log_repository import ExecutionLogRepository
from src.infrastructure.repositories.test_execution_repository import TestExecutionRepository


class UnitOfWork:
    """Async Unit of Work to manage a single DB transaction."""

    def __init__(self, session_factory: Callable[[], AsyncSession]) -> None:
        self._session_factory = session_factory
        self.session: AsyncSession | None = None
        self.test_execution_repo: TestExecutionRepository | None = None
        self.execution_log_repo: ExecutionLogRepository | None = None

    async def __aenter__(self) -> UnitOfWork:
        self.session = self._session_factory()
        self.test_execution_repo = TestExecutionRepository(self.session)
        self.execution_log_repo = ExecutionLogRepository(self.session)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        if self.session is None:
            return False
        try:
            if exc:
                await self.session.rollback()
            else:
                await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        finally:
            await self.session.close()
        return False

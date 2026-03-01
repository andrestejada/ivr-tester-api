"""Database models package.

Importing this package registers all ORM models with Base.metadata,
which is required by Alembic for autogenerate support.
"""

from src.infrastructure.database.models.execution_log import ExecutionLogModel
from src.infrastructure.database.models.ivr_architecture import IVRArchitectureModel
from src.infrastructure.database.models.profile import ProfileModel
from src.infrastructure.database.models.test_case import TestCaseModel
from src.infrastructure.database.models.test_execution import TestExecutionModel, TestStatus

__all__ = [
    "ProfileModel",
    "IVRArchitectureModel",
    "TestCaseModel",
    "TestExecutionModel",
    "TestStatus",
    "ExecutionLogModel",
]

"""Use case for listing test executions by test case."""

from uuid import UUID

from src.application.dtos import TestExecutionResponse
from src.domain.repositories.test_execution_repository import ITestExecutionRepository


class ListTestExecutionsUseCase:
    """Use case para listar ejecuciones de un Test Case."""

    def __init__(self, repository: ITestExecutionRepository):
        self.repository = repository

    async def execute(self, test_case_id: UUID) -> list[TestExecutionResponse]:
        """Ejecuta el listado.

        Args:
            test_case_id: ID del test case padre.

        Returns:
            Lista de TestExecutionResponse.
        """
        executions = await self.repository.list_by_test_case(test_case_id)
        return [
            TestExecutionResponse(
                id=e.id,
                test_case_id=e.test_case_id,
                status=e.status,
                duration_seconds=e.duration_seconds,
                provider_call_sid=e.provider_call_sid,
                executed_at=e.executed_at,
            )
            for e in executions
        ]

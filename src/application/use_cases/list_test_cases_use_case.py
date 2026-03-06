"""Use case for listing Test Cases by architecture."""

from uuid import UUID

from src.application.dtos import TestCaseResponse
from src.domain.repositories.test_case_repository import ITestCaseRepository


class ListTestCasesUseCase:
    """Use case para listar Test Cases de una arquitectura IVR."""

    def __init__(self, repository: ITestCaseRepository):
        self.repository = repository

    async def execute(self, ivr_architecture_id: UUID) -> list[TestCaseResponse]:
        """Ejecuta el listado de Test Cases.

        Args:
            ivr_architecture_id: ID de la arquitectura IVR.

        Returns:
            Lista de TestCaseResponse.
        """
        test_cases = await self.repository.list_by_architecture(
            ivr_architecture_id
        )
        return [
            TestCaseResponse(
                id=tc.id,
                ivr_architecture_id=tc.ivr_architecture_id,
                name=tc.name,
                flow_script=tc.flow_script,
                created_at=tc.created_at,
            )
            for tc in test_cases
        ]

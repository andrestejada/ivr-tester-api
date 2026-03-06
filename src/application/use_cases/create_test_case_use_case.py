"""Use case for creating a Test Case."""

from uuid import UUID

from src.domain.repositories.test_case_repository import ITestCaseRepository


class CreateTestCaseUseCase:
    """Use case para crear un nuevo Test Case."""

    def __init__(self, repository: ITestCaseRepository):
        self.repository = repository

    async def execute(
        self,
        ivr_architecture_id: UUID,
        name: str,
        flow_script: list[dict],
    ) -> UUID:
        """Ejecuta la creación de un Test Case.

        Args:
            ivr_architecture_id: ID de la arquitectura IVR.
            name: Nombre del caso de prueba.
            flow_script: Lista de pasos del flujo.

        Returns:
            UUID del test case creado.
        """
        return await self.repository.create(
            ivr_architecture_id=ivr_architecture_id,
            name=name,
            flow_script=flow_script,
        )

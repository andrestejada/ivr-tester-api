"""Use case for updating an existing Test Case."""

from uuid import UUID

from src.domain.repositories.test_case_repository import ITestCaseRepository


class UpdateTestCaseUseCase:
    """Use case para actualizar un Test Case existente."""

    def __init__(self, repository: ITestCaseRepository):
        self.repository = repository

    async def execute(
        self,
        test_case_id: UUID,
        name: str | None = None,
        flow_script: list[dict] | None = None,
    ) -> None:
        """Ejecuta la actualización de un Test Case.

        Args:
            test_case_id: ID del test case a actualizar.
            name: Nuevo nombre del caso de prueba (opcional).
            flow_script: Nueva lista de pasos del flujo (opcional).

        Raises:
            NotFoundError: Si el test case no existe.
        """
        if name is None and flow_script is None:
            raise ValueError("At least one field (name or flow_script) must be provided")
        
        await self.repository.update(
            test_case_id=test_case_id,
            name=name,
            flow_script=flow_script,
        )

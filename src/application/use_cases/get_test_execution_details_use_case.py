"""Use case for retrieving complete test execution details with forensic logs."""

from uuid import UUID

from src.application.dtos.test_execution_details import TestExecutionDetailsResponse
from src.domain.repositories.test_execution_repository import ITestExecutionRepository


class GetTestExecutionDetailsUseCase:
    """Use case para obtener los detalles completos de una ejecución.
    
    Retorna la ejecución junto con:
    - TestCase asociado
    - IVRArchitecture del TestCase
    - Todos los logs de ejecución ordenados por step_number
    """

    def __init__(self, repository: ITestExecutionRepository):
        self.repository = repository

    async def execute(self, execution_id: UUID) -> TestExecutionDetailsResponse:
        """Ejecuta la obtención de detalles completos.

        Args:
            execution_id: ID de la ejecución a analizar.

        Returns:
            TestExecutionDetailsResponse con toda la información anidada.
            
        Raises:
            NotFoundError: Si la ejecución no existe.
        """
        # Obtiene la ejecución con todas las relaciones precargadas
        execution_model = await self.repository.get_by_id_with_details(execution_id)
        
        # Mapea el modelo ORM al DTO (from_attributes=True maneja las relaciones)
        return TestExecutionDetailsResponse.model_validate(execution_model)

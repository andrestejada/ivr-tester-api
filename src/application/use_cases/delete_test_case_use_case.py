from uuid import UUID

from src.application.exceptions import NotFoundError
from src.domain.repositories.ivr_architecture_repository import IIVRArchitectureRepository
from src.domain.repositories.test_case_repository import ITestCaseRepository
from src.domain.repositories.test_execution_repository import ITestExecutionRepository
from src.infrastructure.call_session_store import CallSessionStore
from src.infrastructure.execution_event_hub import ExecutionEventHub


class DeleteTestCaseUseCase:
    def __init__(
        self,
        architecture_repository: IIVRArchitectureRepository,
        test_case_repository: ITestCaseRepository,
        test_execution_repository: ITestExecutionRepository,
        event_hub: ExecutionEventHub,
        call_session_store: CallSessionStore,
    ):
        self.architecture_repository = architecture_repository
        self.test_case_repository = test_case_repository
        self.test_execution_repository = test_execution_repository
        self.event_hub = event_hub
        self.call_session_store = call_session_store

    async def execute(
        self,
        architecture_id: UUID,
        test_case_id: UUID,
        user_id: UUID,
    ) -> None:
        architecture = await self.architecture_repository.get_by_id(architecture_id)
        if architecture.user_id != user_id:
            raise NotFoundError(f"IVR Architecture {architecture_id} not found")

        test_case = await self.test_case_repository.get_by_id(test_case_id)
        if test_case.ivr_architecture_id != architecture_id:
            raise NotFoundError(f"Test Case {test_case_id} not found")

        executions = await self.test_execution_repository.list_by_test_case(test_case_id)
        for execution in executions:
            await self.event_hub.close_execution(execution.id)
            if execution.provider_call_sid:
                await self.call_session_store.close_session(execution.provider_call_sid)

        await self.test_case_repository.delete(test_case_id)

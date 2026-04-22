from uuid import UUID

from src.application.exceptions import NotFoundError
from src.domain.repositories.ivr_architecture_repository import IIVRArchitectureRepository
from src.domain.repositories.test_case_repository import ITestCaseRepository
from src.domain.repositories.test_execution_repository import ITestExecutionRepository
from src.infrastructure.call_session_store import CallSessionStore
from src.infrastructure.execution_event_hub import ExecutionEventHub


class DeleteIVRArchitectureUseCase:
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

    async def execute(self, architecture_id: UUID, user_id: UUID) -> None:
        architecture = await self.architecture_repository.get_by_id(architecture_id)
        if architecture.user_id != user_id:
            raise NotFoundError(f"IVR Architecture {architecture_id} not found")

        test_cases = await self.test_case_repository.list_by_architecture(architecture_id)
        for test_case in test_cases:
            executions = await self.test_execution_repository.list_by_test_case(test_case.id)
            for execution in executions:
                await self.event_hub.close_execution(execution.id)
                if execution.provider_call_sid:
                    await self.call_session_store.close_session(execution.provider_call_sid)

        await self.architecture_repository.delete(
            architecture_id=architecture_id,
            user_id=user_id,
        )

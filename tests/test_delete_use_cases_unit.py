"""Unit tests for delete use cases with resource cleanup coverage."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, call
from uuid import UUID

import pytest

from src.application.exceptions import NotFoundError
from src.application.use_cases.delete_ivr_architecture_use_case import (
    DeleteIVRArchitectureUseCase,
)
from src.application.use_cases.delete_test_case_use_case import DeleteTestCaseUseCase


class TestDeleteTestCaseUseCase:
    @pytest.fixture
    def architecture_id(self) -> UUID:
        return UUID("550e8400-e29b-41d4-a716-446655440000")

    @pytest.fixture
    def test_case_id(self) -> UUID:
        return UUID("550e8400-e29b-41d4-a716-446655440001")

    @pytest.fixture
    def user_id(self) -> UUID:
        return UUID("550e8400-e29b-41d4-a716-446655440002")

    @pytest.fixture
    def architecture_repository(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture
    def test_case_repository(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture
    def test_execution_repository(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture
    def event_hub(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture
    def call_session_store(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture
    def use_case(
        self,
        architecture_repository: AsyncMock,
        test_case_repository: AsyncMock,
        test_execution_repository: AsyncMock,
        event_hub: AsyncMock,
        call_session_store: AsyncMock,
    ) -> DeleteTestCaseUseCase:
        return DeleteTestCaseUseCase(
            architecture_repository=architecture_repository,
            test_case_repository=test_case_repository,
            test_execution_repository=test_execution_repository,
            event_hub=event_hub,
            call_session_store=call_session_store,
        )

    @pytest.mark.asyncio
    async def test_execute_deletes_test_case_and_cleans_resources(
        self,
        use_case: DeleteTestCaseUseCase,
        architecture_repository: AsyncMock,
        test_case_repository: AsyncMock,
        test_execution_repository: AsyncMock,
        event_hub: AsyncMock,
        call_session_store: AsyncMock,
        architecture_id: UUID,
        test_case_id: UUID,
        user_id: UUID,
    ) -> None:
        architecture_repository.get_by_id.return_value = SimpleNamespace(user_id=user_id)
        test_case_repository.get_by_id.return_value = SimpleNamespace(
            ivr_architecture_id=architecture_id
        )
        exec_1 = SimpleNamespace(id=UUID("550e8400-e29b-41d4-a716-446655440010"), provider_call_sid="CA001")
        exec_2 = SimpleNamespace(id=UUID("550e8400-e29b-41d4-a716-446655440011"), provider_call_sid=None)
        test_execution_repository.list_by_test_case.return_value = [exec_1, exec_2]

        await use_case.execute(
            architecture_id=architecture_id,
            test_case_id=test_case_id,
            user_id=user_id,
        )

        event_hub.close_execution.assert_has_awaits([call(exec_1.id), call(exec_2.id)])
        call_session_store.close_session.assert_awaited_once_with("CA001")
        test_case_repository.delete.assert_awaited_once_with(test_case_id)

    @pytest.mark.asyncio
    async def test_execute_raises_not_found_when_architecture_belongs_to_other_user(
        self,
        use_case: DeleteTestCaseUseCase,
        architecture_repository: AsyncMock,
        test_case_repository: AsyncMock,
        test_execution_repository: AsyncMock,
        architecture_id: UUID,
        test_case_id: UUID,
        user_id: UUID,
    ) -> None:
        architecture_repository.get_by_id.return_value = SimpleNamespace(
            user_id=UUID("550e8400-e29b-41d4-a716-446655440099")
        )

        with pytest.raises(NotFoundError, match="IVR Architecture"):
            await use_case.execute(
                architecture_id=architecture_id,
                test_case_id=test_case_id,
                user_id=user_id,
            )

        test_case_repository.get_by_id.assert_not_awaited()
        test_execution_repository.list_by_test_case.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_execute_raises_not_found_when_test_case_is_not_in_architecture(
        self,
        use_case: DeleteTestCaseUseCase,
        architecture_repository: AsyncMock,
        test_case_repository: AsyncMock,
        test_execution_repository: AsyncMock,
        architecture_id: UUID,
        test_case_id: UUID,
        user_id: UUID,
    ) -> None:
        architecture_repository.get_by_id.return_value = SimpleNamespace(user_id=user_id)
        test_case_repository.get_by_id.return_value = SimpleNamespace(
            ivr_architecture_id=UUID("550e8400-e29b-41d4-a716-446655440123")
        )

        with pytest.raises(NotFoundError, match="Test Case"):
            await use_case.execute(
                architecture_id=architecture_id,
                test_case_id=test_case_id,
                user_id=user_id,
            )

        test_execution_repository.list_by_test_case.assert_not_awaited()


class TestDeleteIVRArchitectureUseCase:
    @pytest.fixture
    def architecture_id(self) -> UUID:
        return UUID("550e8400-e29b-41d4-a716-446655440200")

    @pytest.fixture
    def user_id(self) -> UUID:
        return UUID("550e8400-e29b-41d4-a716-446655440201")

    @pytest.fixture
    def architecture_repository(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture
    def test_case_repository(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture
    def test_execution_repository(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture
    def event_hub(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture
    def call_session_store(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture
    def use_case(
        self,
        architecture_repository: AsyncMock,
        test_case_repository: AsyncMock,
        test_execution_repository: AsyncMock,
        event_hub: AsyncMock,
        call_session_store: AsyncMock,
    ) -> DeleteIVRArchitectureUseCase:
        return DeleteIVRArchitectureUseCase(
            architecture_repository=architecture_repository,
            test_case_repository=test_case_repository,
            test_execution_repository=test_execution_repository,
            event_hub=event_hub,
            call_session_store=call_session_store,
        )

    @pytest.mark.asyncio
    async def test_execute_deletes_architecture_and_cleans_nested_resources(
        self,
        use_case: DeleteIVRArchitectureUseCase,
        architecture_repository: AsyncMock,
        test_case_repository: AsyncMock,
        test_execution_repository: AsyncMock,
        event_hub: AsyncMock,
        call_session_store: AsyncMock,
        architecture_id: UUID,
        user_id: UUID,
    ) -> None:
        architecture_repository.get_by_id.return_value = SimpleNamespace(user_id=user_id)

        test_case_1 = SimpleNamespace(id=UUID("550e8400-e29b-41d4-a716-446655440210"))
        test_case_2 = SimpleNamespace(id=UUID("550e8400-e29b-41d4-a716-446655440211"))
        test_case_repository.list_by_architecture.return_value = [test_case_1, test_case_2]

        exec_a = SimpleNamespace(id=UUID("550e8400-e29b-41d4-a716-446655440220"), provider_call_sid="CAA")
        exec_b = SimpleNamespace(id=UUID("550e8400-e29b-41d4-a716-446655440221"), provider_call_sid=None)
        exec_c = SimpleNamespace(id=UUID("550e8400-e29b-41d4-a716-446655440222"), provider_call_sid="CAC")
        test_execution_repository.list_by_test_case.side_effect = [[exec_a, exec_b], [exec_c]]

        await use_case.execute(architecture_id=architecture_id, user_id=user_id)

        assert test_execution_repository.list_by_test_case.await_count == 2
        event_hub.close_execution.assert_has_awaits(
            [call(exec_a.id), call(exec_b.id), call(exec_c.id)]
        )
        call_session_store.close_session.assert_has_awaits([call("CAA"), call("CAC")])
        architecture_repository.delete.assert_awaited_once_with(
            architecture_id=architecture_id,
            user_id=user_id,
        )

    @pytest.mark.asyncio
    async def test_execute_raises_not_found_when_architecture_belongs_to_other_user(
        self,
        use_case: DeleteIVRArchitectureUseCase,
        architecture_repository: AsyncMock,
        test_case_repository: AsyncMock,
        test_execution_repository: AsyncMock,
        architecture_id: UUID,
        user_id: UUID,
    ) -> None:
        architecture_repository.get_by_id.return_value = SimpleNamespace(
            user_id=UUID("550e8400-e29b-41d4-a716-446655440299")
        )

        with pytest.raises(NotFoundError, match="IVR Architecture"):
            await use_case.execute(architecture_id=architecture_id, user_id=user_id)

        test_case_repository.list_by_architecture.assert_not_awaited()
        test_execution_repository.list_by_test_case.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_execute_deletes_architecture_when_it_has_no_test_cases(
        self,
        use_case: DeleteIVRArchitectureUseCase,
        architecture_repository: AsyncMock,
        test_case_repository: AsyncMock,
        test_execution_repository: AsyncMock,
        event_hub: AsyncMock,
        call_session_store: AsyncMock,
        architecture_id: UUID,
        user_id: UUID,
    ) -> None:
        architecture_repository.get_by_id.return_value = SimpleNamespace(user_id=user_id)
        test_case_repository.list_by_architecture.return_value = []

        await use_case.execute(architecture_id=architecture_id, user_id=user_id)

        test_execution_repository.list_by_test_case.assert_not_awaited()
        event_hub.close_execution.assert_not_awaited()
        call_session_store.close_session.assert_not_awaited()
        architecture_repository.delete.assert_awaited_once_with(
            architecture_id=architecture_id,
            user_id=user_id,
        )

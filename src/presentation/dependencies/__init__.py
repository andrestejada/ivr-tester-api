from src.presentation.dependencies.ivr_architecture_dependencies import (
    get_create_ivr_architecture_use_case,
    get_delete_ivr_architecture_use_case,
    get_list_ivr_architectures_use_case,
    get_update_ivr_architecture_use_case,
)
from src.presentation.dependencies.test_case_dependencies import (
    get_create_test_case_use_case,
    get_delete_test_case_use_case,
    get_list_test_cases_use_case,
    get_update_test_case_use_case,
)
from src.presentation.dependencies.test_execution_dependencies import (
    get_list_test_executions_use_case,
    get_test_execution_details_use_case,
    get_execution_analytics_use_case,
    get_test_execution_repo,
)

__all__ = [
    "get_create_ivr_architecture_use_case",
    "get_delete_ivr_architecture_use_case",
    "get_list_ivr_architectures_use_case",
    "get_update_ivr_architecture_use_case",
    "get_create_test_case_use_case",
    "get_delete_test_case_use_case",
    "get_list_test_cases_use_case",
    "get_update_test_case_use_case",
    "get_list_test_executions_use_case",
    "get_test_execution_details_use_case",
    "get_execution_analytics_use_case",
    "get_test_execution_repo",
]

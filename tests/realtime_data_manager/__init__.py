"""
Comprehensive test suite for project_x_py.realtime_data_manager module.

This test suite follows the project's proven TDD methodology:
1. Tests define expected behavior, not current implementation
2. Write tests first, then fix implementation if needed
3. Never modify tests to match buggy code
4. Comprehensive coverage including edge cases and error conditions

Test Structure:
- test_core.py: Main RealtimeDataManager class functionality
- test_callbacks.py: Callback system and event handling
- test_data_processing.py: OHLCV data processing and bar creation
- test_data_access.py: Data retrieval and query methods
- test_memory_management.py: Memory optimization and cleanup
- test_validation.py: Input validation and error handling
- test_dataframe_optimization.py: Lazy DataFrame operations
- test_dst_handling.py: Daylight Saving Time handling
- test_dynamic_resource_limits.py: Resource management
- test_mmap_overflow.py: Memory-mapped storage overflow

Coverage Goals:
- >90% code coverage for all modules
- All critical paths tested
- Error conditions and edge cases covered
- Thread safety and async behavior validated
- Integration with other components tested

This follows the same successful pattern used for:
- order_manager/ (69% -> target >90%)
- position_manager/ (86% coverage, 117 tests)
- realtime/ (87% coverage, 230 tests)
- utils/ (92-100% coverage across 7 modules)
"""

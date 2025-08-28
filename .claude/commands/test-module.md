  ## Objective:

  Your primary goal is to develop a comprehensive test suite for the src/project_x_py/{{module}}/ module, ensuring its logic is robust and correct. You will strictly adhere to the project's Test-Driven
  Development (TDD) methodology.

  ## Core Instructions:

   1. **Understand the Framework**: Begin by thoroughly reading CLAUDE.md. This document contains critical information about the project's architecture, coding standards, and the TDD principles we adhere to. Pay close
      attention to the TDD section, as it is the foundation for this task.

   2. **Review Proven Patterns**: Access and apply our established TDD development pattern from your memory. This pattern dictates that tests are written before the implementation and serve as the ultimate
      specification for the code's behavior.

   3. **Assess Current Status**: Read the v3.3.6 Testing Summary to get a clear picture of the current testing landscape for the {{module}} module. This will help you identify areas that are untested or need more
      thorough validation.

   4. **TDD for `{{module}}`**:
       * Audit Existing Tests: Before writing new tests, critically evaluate any existing tests for the {{module}}. Your audit must confirm that they are testing for the correct behavior and not simply mirroring
         flawed logic in the current implementation.
       * Follow the TDD Cycle: For all new tests, you must follow the **Red-Green-Refactor cycle**:
           1. Red: Write a failing test that defines the desired functionality.
           2. Green: Write the minimal code necessary to make the test pass.
           3. Refactor: Improve the code's design and quality while ensuring all tests remain green.
       * **Bug Discovery**: The primary goal of this TDD approach is to uncover any bugs in the core logic. If a test fails, it is because the implementation is incorrect, not the test. Fix the code to match the
         test's expectations.

  ## Final Deliverable:

  A complete set of tests for the src/project_x_py/{{module}}/ module that provides full coverage and validates the correctness of its logic. This test suite will serve as the definitive specification for the
  module's behavior.

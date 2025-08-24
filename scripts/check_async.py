#!/usr/bin/env python3
"""
Check for 100% async compliance in project-x-py SDK.
Python 3.12+ compatible.
"""

import ast
import sys
from pathlib import Path


class AsyncChecker(ast.NodeVisitor):
    """Check for synchronous methods in async classes."""

    def __init__(self, filename: str):
        self.filename = filename
        self.issues: list[tuple[int, str]] = []
        self.in_async_class = False
        self.class_stack: list[str] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Check if class should be async."""
        self.class_stack.append(node.name)

        # Check if class has any async methods
        has_async = any(isinstance(item, ast.AsyncFunctionDef) for item in node.body)

        # Explicitly exclude utility classes that don't need to be async
        excluded_classes = [
            "ConfigManager",  # Configuration management - sync utility
            "ErrorContext",  # Error context manager - has async context but methods can be sync
            "Deprecation",  # Deprecation utilities
            "Logger",  # Logging utilities
        ]

        if node.name in excluded_classes:
            is_async_class = False
        else:
            # Check if it's a class that should be async based on patterns
            is_async_class = (
                (
                    "Manager" in node.name and node.name != "ConfigManager"
                )  # Managers except ConfigManager
                or "Client" in node.name
                or "Suite" in node.name
                or "Realtime" in node.name
                or "OrderBook" in node.name  # OrderBook is async
                or "DataManager" in node.name  # Data managers are async
                or has_async  # Any class with async methods
            )

        old_in_async = self.in_async_class
        if is_async_class:
            self.in_async_class = True

        self.generic_visit(node)

        self.in_async_class = old_in_async
        self.class_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Check for sync methods in async classes."""
        if self.in_async_class:
            # Skip special methods and private methods
            if not (
                node.name.startswith("__")
                or node.name.startswith("_")
                or node.name in ["__init__", "__str__", "__repr__"]
                or "@property"
                in [d.id for d in node.decorator_list if isinstance(d, ast.Name)]
                or "@staticmethod"
                in [d.id for d in node.decorator_list if isinstance(d, ast.Name)]
                or "@classmethod"
                in [d.id for d in node.decorator_list if isinstance(d, ast.Name)]
            ):
                # Check if method performs I/O operations
                if self._has_io_operations(node):
                    class_name = ".".join(self.class_stack)
                    self.issues.append(
                        (
                            node.lineno,
                            f"Synchronous method '{node.name}' in async class '{class_name}' performs I/O",
                        )
                    )

        self.generic_visit(node)

    def _has_io_operations(self, node: ast.FunctionDef) -> bool:
        """Check if function has actual I/O operations."""
        # Skip simple getter methods that just return values
        if node.name.startswith("get_") and self._is_simple_getter(node):
            return False

        for item in ast.walk(node):
            if isinstance(item, ast.Call):
                if isinstance(item.func, ast.Attribute):
                    # Check for actual I/O operations on known I/O objects
                    attr_name = item.func.attr

                    # Get the object being called on
                    if isinstance(item.func.value, ast.Name):
                        obj_name = item.func.value.id

                        # Check for known I/O objects and their methods
                        if obj_name in ["httpx", "aiohttp", "requests", "urllib"]:
                            if attr_name in [
                                "get",
                                "post",
                                "put",
                                "delete",
                                "patch",
                                "request",
                            ]:
                                return True
                        elif obj_name in ["socket", "websocket", "ws"]:
                            if attr_name in ["connect", "send", "recv", "close"]:
                                return True
                        elif obj_name in ["file", "f", "fp"]:
                            if attr_name in ["read", "write", "seek", "tell"]:
                                return True
                        elif obj_name in [
                            "db",
                            "database",
                            "conn",
                            "connection",
                            "cursor",
                        ]:
                            if attr_name in ["execute", "fetch", "commit", "rollback"]:
                                return True

                    # Check for self.client or self.http calls (common in SDK)
                    if isinstance(item.func.value, ast.Attribute):
                        if hasattr(item.func.value, "attr"):
                            obj_attr = item.func.value.attr
                            if obj_attr in [
                                "client",
                                "http",
                                "session",
                                "api",
                                "_client",
                                "_http",
                            ]:
                                if attr_name in [
                                    "get",
                                    "post",
                                    "put",
                                    "delete",
                                    "patch",
                                    "request",
                                    "fetch",
                                ]:
                                    return True

                    # Check for common async I/O patterns that should be async
                    if attr_name in [
                        "request",
                        "fetch_data",
                        "api_call",
                        "send_request",
                        "make_request",
                        "http_get",
                        "http_post",
                    ]:
                        return True

                elif isinstance(item.func, ast.Name):
                    # Check for built-in I/O functions
                    if item.func.id in ["open", "print", "input"]:
                        return True
                    # Check for common I/O function names
                    if item.func.id in ["fetch", "request", "download", "upload"]:
                        return True

        return False

    def _is_simple_getter(self, node: ast.FunctionDef) -> bool:
        """Check if a method is a simple getter that doesn't perform I/O."""
        # Simple getters typically have a single return statement or simple logic
        if len(node.body) == 1 and isinstance(node.body[0], ast.Return):
            return True

        # Check for simple property-like getters with basic logic
        has_io_call = False
        for item in ast.walk(node):
            if isinstance(item, ast.Call):
                # Check if any calls might be I/O
                if isinstance(item.func, ast.Attribute):
                    if item.func.attr in [
                        "request",
                        "fetch",
                        "api_call",
                        "http_get",
                        "http_post",
                    ]:
                        has_io_call = True
                        break
                elif isinstance(item.func, ast.Name):
                    if item.func.id in ["open", "fetch", "request"]:
                        has_io_call = True
                        break

        # If no I/O calls and the method is short, it's likely a simple getter
        if not has_io_call and len(node.body) <= 10:
            return True

        return False


def check_file(filepath: Path) -> list[tuple[str, int, str]]:
    """Check a single file for async compliance."""
    try:
        with open(filepath, encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=str(filepath))
    except SyntaxError as e:
        return [(str(filepath), e.lineno or 0, f"Syntax error: {e.msg}")]

    checker = AsyncChecker(str(filepath))
    checker.visit(tree)

    return [(str(filepath), line, msg) for line, msg in checker.issues]


def main() -> int:
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: check_async.py <file1> [file2] ...")
        return 1

    all_issues = []
    for filepath in sys.argv[1:]:
        path = Path(filepath)
        if path.exists() and path.suffix == ".py":
            issues = check_file(path)
            all_issues.extend(issues)

    if all_issues:
        print("Async compliance issues found:")
        for filepath, line, msg in all_issues:
            print(f"  {filepath}:{line}: {msg}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())

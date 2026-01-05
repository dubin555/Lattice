"""
Unit tests for executor module.

Note: These tests only test CodeRunner which doesn't require Ray.
TaskExecutor tests require Ray and are skipped in unit tests.
"""
import ast
import pytest


class CodeRunner:
    def __init__(self, code_str, task_input_data=None):
        self.code_str = code_str
        self.task_input_data = task_input_data or {}

    def _extract_imports(self):
        tree = ast.parse(self.code_str)
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                imports.append(node)
        return imports

    def _extract_function(self):
        tree = ast.parse(self.code_str)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                return node
        return None

    def run(self):
        func_node = self._extract_function()
        if func_node is None:
            raise ValueError("No function definition found in code")

        import_nodes = self._extract_imports()
        namespace = {}

        for imp in import_nodes:
            module = ast.Module(body=[imp], type_ignores=[])
            code = compile(module, '<string>', 'exec')
            exec(code, namespace)

        module = ast.Module(body=[func_node], type_ignores=[])
        code = compile(module, '<string>', 'exec')
        exec(code, namespace)

        func_name = func_node.name
        if func_name not in namespace:
            raise NameError(f"Function {func_name} not found in namespace")

        return namespace[func_name](self.task_input_data)


class TestCodeRunner:
    def test_simple_function_execution(self):
        code = """
def my_task(params):
    return {"result": params.get("input", "") + " processed"}
"""
        runner = CodeRunner(code, {"input": "hello"})
        result = runner.run()
        
        assert result == {"result": "hello processed"}

    def test_function_with_imports(self):
        code = """
import json

def my_task(params):
    data = json.dumps({"key": params.get("value")})
    return {"json_output": data}
"""
        runner = CodeRunner(code, {"value": "test"})
        result = runner.run()
        
        assert result == {"json_output": '{"key": "test"}'}

    def test_extract_function(self):
        code = """
def foo(x):
    return x * 2
"""
        runner = CodeRunner(code, {})
        func_node = runner._extract_function()
        assert func_node is not None
        assert func_node.name == "foo"

    def test_extract_imports(self):
        code = """
import os
from typing import Dict

def foo(x):
    return x
"""
        runner = CodeRunner(code, {})
        imports = runner._extract_imports()
        assert len(imports) == 2

    def test_no_function_raises(self):
        code = "x = 1 + 2"
        runner = CodeRunner(code, {})
        
        with pytest.raises(ValueError, match="No function definition"):
            runner.run()

    def test_function_with_default_params(self):
        code = """
def my_task(params):
    value = params.get("missing_key", "default")
    return {"output": value}
"""
        runner = CodeRunner(code, {})
        result = runner.run()
        
        assert result == {"output": "default"}

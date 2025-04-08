import re
import ast
import builtins
from collections import Counter

class CodeAnalyzer:
    """Analyzes Python code to provide intelligent suggestions and error detection."""
    
    def __init__(self, code):
        self.code = code
        self.ast = None
        self.variables = []
        self.functions = []
        self.imports = []
        self.classes = []
        self.patterns = {}
        self.issues = []
        self.syntax_error = None
        self.builtin_functions = dir(builtins)
        
    def parse(self):
        """Parse the code to extract AST and gather insights."""
        try:
            self.ast = ast.parse(self.code)
            self._extract_features()
            return True
        except SyntaxError as e:
            self.syntax_error = {
                'line': e.lineno,
                'offset': e.offset,
                'msg': e.msg
            }
            self.issues.append(f"Syntax error at line {e.lineno}: {e.msg}")
            self._suggest_syntax_fix(e)
            return False
        except Exception as e:
            self.issues.append(f"Error parsing code: {str(e)}")
            return False
    
    def _suggest_syntax_fix(self, error):
        """Suggest fixes for common syntax errors."""
        line_num = error.lineno - 1  # 0-indexed
        lines = self.code.split('\n')
        
        if line_num >= len(lines):
            return
            
        error_line = lines[line_num]
        error_msg = error.msg.lower()
        
        # Missing closing parenthesis/bracket/brace
        if "unexpected EOF" in error_msg or "expected" in error_msg:
            if ")" in error_msg:
                self.issues.append("Suggestion: Check for missing closing parenthesis ')'")
            elif "]" in error_msg:
                self.issues.append("Suggestion: Check for missing closing bracket ']'")
            elif "}" in error_msg:
                self.issues.append("Suggestion: Check for missing closing brace '}'")
            elif ":" in error_msg:
                self.issues.append("Suggestion: Add a colon ':' at the end of the line")
        
        # Indentation errors
        elif "indent" in error_msg:
            if "expected" in error_msg:
                self.issues.append("Suggestion: Increase indentation on this line")
            elif "unexpected" in error_msg:
                self.issues.append("Suggestion: Decrease indentation on this line")
        
        # Invalid syntax
        elif "invalid syntax" in error_msg:
            # Check for common Python mistakes
            if "=" in error_line and "==" not in error_line and error_line.strip().startswith("if "):
                self.issues.append("Suggestion: Use '==' for comparison in if statements, not '='")
            elif "++" in error_line:
                self.issues.append("Suggestion: Python doesn't support '++', use '+= 1' instead")
            elif "--" in error_line:
                self.issues.append("Suggestion: Python doesn't support '--', use '-= 1' instead")
        
        # Missing commas in collections
        elif "expected ',' or" in error_msg:
            self.issues.append("Suggestion: You may be missing a comma between items")
            
        # Undefined variable
        elif "name" in error_msg and "is not defined" in error_msg:
            var_match = re.search(r"name '(\w+)' is not defined", error_msg)
            if var_match:
                var_name = var_match.group(1)
                self.issues.append(f"Suggestion: The variable '{var_name}' is used but not defined")
    
    def _extract_features(self):
        """Extract variables, functions, classes, and imports from AST."""
        for node in ast.walk(self.ast):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                self.variables.append(node.id)
            elif isinstance(node, ast.FunctionDef):
                self.functions.append({
                    'name': node.name,
                    'args': [arg.arg for arg in node.args.args],
                    'line': node.lineno,
                    'body_length': len(node.body)
                })
            elif isinstance(node, ast.ClassDef):
                self.classes.append({
                    'name': node.name,
                    'line': node.lineno,
                    'methods': []
                })
            elif isinstance(node, ast.Import):
                for name in node.names:
                    self.imports.append(name.name)
            elif isinstance(node, ast.ImportFrom):
                self.imports.append(node.module)
    
    def suggest_completion(self, context, cursor_pos):
        """Suggest code completion based on current context."""
        # Simple context-based suggestions
        if context.strip().endswith('for '):
            # Suggest variable to iterate over
            if self.variables:
                return [f"{var} in range(10)" for var in self.variables[:3]]
            else:
                return ["i in range(10)", "item in items", "key, value in data.items()"]
        
        # Check for function call completion
        func_match = re.search(r'(\w+)\($', context.strip())
        if func_match:
            func_name = func_match.group(1)
            # Check if it's a user-defined function
            for func in self.functions:
                if func['name'] == func_name:
                    arg_str = ", ".join(func['args'])
                    return [f"{func_name}({arg_str})"]
            
            # Check if it's a built-in function
            if func_name in self.builtin_functions:
                if func_name == 'print':
                    if self.variables:
                        return [f"print({var})" for var in self.variables[:3]]
                    else:
                        return ['print("Hello, World!")']
                elif func_name == 'len':
                    if self.variables:
                        return [f"len({var})" for var in self.variables[:3]]
                    else:
                        return ['len(items)']
                elif func_name == 'range':
                    return ['range(10)', 'range(0, 10)', 'range(0, 10, 2)']
                elif func_name == 'open':
                    return ['open("filename.txt", "r")', 'open("output.txt", "w")']
        
        # Check for method completion
        method_match = re.search(r'(\w+)\.(\w*)$', context.strip())
        if method_match:
            obj_name = method_match.group(1)
            partial_method = method_match.group(2)
            
            # List of common string methods
            if partial_method.startswith('s'):
                return [
                    f"{obj_name}.strip()",
                    f"{obj_name}.split()",
                    f"{obj_name}.startswith(prefix)"
                ]
            elif partial_method.startswith('r'):
                return [
                    f"{obj_name}.replace(old, new)",
                    f"{obj_name}.rstrip()",
                    f"{obj_name}.rfind(sub)"
                ]
            
            # List of common list methods
            if partial_method.startswith('a'):
                return [f"{obj_name}.append(item)", f"{obj_name}.add(item)"]
            elif partial_method.startswith('r'):
                return [
                    f"{obj_name}.remove(item)",
                    f"{obj_name}.reverse()",
                    f"{obj_name}.replace(old, new)"
                ]
        
        # Default suggestions based on common patterns
        return [
            "def function_name(params):",
            "for item in items:",
            "if condition:",
            "class ClassName:",
            "with open('filename.txt', 'r') as f:",
            "try:\n    # code\nexcept Exception as e:",
            "import module_name"
        ]
    
    def analyze_code_quality(self):
        """Analyze code for quality issues and potential bugs."""
        issues = []
        
        # Check for variable errors
        self._check_variable_usage(issues)
        
        # Check for logical errors
        self._check_logical_issues(issues)
        
        # Check for style issues
        self._check_style_issues(issues)
        
        # Check for code smells
        self._check_code_smells(issues)
        
        return issues
    
    def _check_variable_usage(self, issues):
        """Check for variable-related issues."""
        # Track defined variables
        defined_vars = set(self.variables)
        used_vars = set()
        
        # Find used variables
        for node in ast.walk(self.ast):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                var_name = node.id
                used_vars.add(var_name)
        
        # Undefined variables (excluding built-ins and imports)
        built_ins = set(dir(builtins))
        imports_as_vars = set(self.imports)
        potentially_undefined = used_vars - defined_vars - built_ins - imports_as_vars
        
        for var in potentially_undefined:
            # Skip common module names and likely imported items
            if var not in ['math', 'os', 'sys', 'np', 'pd', 're', 'datetime']:
                issues.append({
                    'type': 'undefined_variable',
                    'message': f"Variable '{var}' may be used before assignment",
                    'line': None,  # Would need more complex analysis to find the line
                    'complexity': 'medium',
                    'fix_suggestion': f"Make sure to initialize '{var}' before using it"
                })
        
        # Unused variables
        unused_vars = defined_vars - used_vars
        for var in unused_vars:
            if not var.startswith('_'):  # Skip variables that start with underscore (conventionally "private")
                issues.append({
                    'type': 'unused_variable',
                    'message': f"Variable '{var}' is defined but never used",
                    'line': None,
                    'complexity': 'simple',
                    'fix_suggestion': f"Remove the unused variable '{var}' or use it in your code"
                })
    
    def _check_logical_issues(self, issues):
        """Check for logical issues in the code."""
        # Check for empty code blocks
        for node in ast.walk(self.ast):
            if isinstance(node, ast.FunctionDef) and len(node.body) == 0:
                issues.append({
                    'type': 'empty_function',
                    'message': f"Function '{node.name}' has an empty body",
                    'line': node.lineno,
                    'complexity': 'simple',
                    'fix_suggestion': f"Add code to implement function '{node.name}' or use 'pass' as a placeholder"
                })
            elif isinstance(node, ast.If) and len(node.body) == 0:
                issues.append({
                    'type': 'empty_if',
                    'message': "If statement has an empty body",
                    'line': node.lineno,
                    'complexity': 'simple',
                    'fix_suggestion': "Add code inside the if block or use 'pass' as a placeholder"
                })
        
        # Check for unreachable code after return/break/continue
        for node in ast.walk(self.ast):
            if isinstance(node, ast.FunctionDef):
                has_return = False
                for i, stmt in enumerate(node.body[:-1]):  # Skip the last statement
                    if isinstance(stmt, ast.Return):
                        has_return = True
                    elif has_return:
                        issues.append({
                            'type': 'unreachable_code',
                            'message': f"Unreachable code in function '{node.name}' after return statement",
                            'line': stmt.lineno,
                            'complexity': 'medium',
                            'fix_suggestion': "Code after a return statement will never execute"
                        })
                        break
    
    def _check_style_issues(self, issues):
        """Check for code style issues."""
        # Check variable naming conventions
        non_snake_case = [var for var in self.variables if not re.match(r'^[a-z_][a-z0-9_]*$', var)]
        if non_snake_case:
            for var in non_snake_case:
                snake_case = re.sub(r'(?<!^)(?=[A-Z])', '_', var).lower()
                issues.append({
                    'type': 'naming_convention',
                    'message': f"Variable '{var}' doesn't follow snake_case convention",
                    'line': None,
                    'complexity': 'simple',
                    'fix_suggestion': f"Rename '{var}' to '{snake_case}'"
                })
        
        # Check function naming conventions
        for func in self.functions:
            if not re.match(r'^[a-z_][a-z0-9_]*$', func['name']):
                snake_case = re.sub(r'(?<!^)(?=[A-Z])', '_', func['name']).lower()
                issues.append({
                    'type': 'naming_convention',
                    'message': f"Function '{func['name']}' doesn't follow snake_case convention",
                    'line': func['line'],
                    'complexity': 'simple',
                    'fix_suggestion': f"Rename '{func['name']}' to '{snake_case}'"
                })
        
        # Check class naming conventions
        for cls in self.classes:
            if not re.match(r'^[A-Z][a-zA-Z0-9]*$', cls['name']):
                pascal_case = ''.join(word.capitalize() for word in re.sub(r'[^a-zA-Z0-9]', ' ', cls['name']).split())
                issues.append({
                    'type': 'naming_convention',
                    'message': f"Class '{cls['name']}' doesn't follow PascalCase convention",
                    'line': cls['line'],
                    'complexity': 'simple',
                    'fix_suggestion': f"Rename '{cls['name']}' to '{pascal_case}'"
                })
    
    def _check_code_smells(self, issues):
        """Check for code smells and design issues."""
        # Check for long functions
        for func in self.functions:
            if func['body_length'] > 15:
                issues.append({
                    'type': 'long_function',
                    'message': f"Function '{func['name']}' is too long ({func['body_length']} lines)",
                    'line': func['line'],
                    'complexity': 'medium',
                    'fix_suggestion': f"Break down '{func['name']}' into smaller, more focused functions"
                })
        
        # Check for repeated code patterns
        code_lines = self.code.split('\n')
        line_patterns = []
        for i in range(len(code_lines) - 3):
            pattern = '\n'.join(code_lines[i:i+3])
            line_patterns.append(pattern)
        
        pattern_counts = Counter(line_patterns)
        repeated_patterns = [p for p, count in pattern_counts.items() if count > 1]
        
        if repeated_patterns:
            issues.append({
                'type': 'repeated_code',
                'message': "Detected repeated code patterns",
                'line': None,
                'complexity': 'complex',
                'fix_suggestion': "Extract repeated code into functions to improve maintainability"
            })
        
        # Check for unused imports
        imported_modules = set(self.imports)
        used_modules = set()
        for node in ast.walk(self.ast):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                parts = node.id.split('.')
                if parts[0] in imported_modules:
                    used_modules.add(parts[0])
        
        unused_imports = imported_modules - used_modules
        if unused_imports:
            issues.append({
                'type': 'unused_imports',
                'message': f"Unused imports: {', '.join(unused_imports)}",
                'line': 1,  # Imports usually at the top
                'complexity': 'simple',
                'fix_suggestion': f"Remove unused imports: {', '.join(unused_imports)}"
            })
    
    def suggest_refactoring(self):
        """Analyze code and suggest refactoring improvements."""
        # Combine all issues and return them
        all_issues = []
        
        # Only analyze if syntax is correct
        if self.syntax_error is None:
            all_issues.extend(self.analyze_code_quality())
        
        return all_issues


class CodeRefactorer:
    """Provides refactoring solutions for identified issues."""
    
    def __init__(self, code, issues):
        self.code = code
        self.issues = issues
        self.refactored_code = code
        
    def apply_refactorings(self):
        """Apply suggested refactorings to the code."""
        for issue in self.issues:
            if issue['type'] == 'unused_imports':
                self._remove_unused_imports(issue)
            elif issue['type'] == 'naming_convention':
                self._fix_naming_conventions(issue)
            elif issue['type'] == 'unused_variable':
                self._remove_unused_variables(issue)
        
        return self.refactored_code
    
    def _remove_unused_imports(self, issue):
        """Remove unused imports from the code."""
        lines = self.refactored_code.split('\n')
        unused_modules = issue['message'].split(': ')[1].split(', ')
        
        # Filter out import lines with unused modules
        result_lines = []
        for line in lines:
            skip = False
            for module in unused_modules:
                if re.search(rf'^\s*import\s+{module}\b', line) or re.search(rf'^\s*from\s+{module}\s+import', line):
                    skip = True
                    break
            if not skip:
                result_lines.append(line)
        
        self.refactored_code = '\n'.join(result_lines)
    
    def _fix_naming_conventions(self, issue):
        """Convert variable names to snake_case or class names to PascalCase."""
        message = issue['message']
        if "doesn't follow snake_case" in message:
            # Extract original and suggested name
            match = re.search(r"'([^']+)' to '([^']+)'", issue['fix_suggestion'])
            if match:
                original_name = match.group(1)
                new_name = match.group(2)
                
                # Replace only the variable/function name (not inside strings or comments)
                pattern = r'(?<![\'"])\b' + re.escape(original_name) + r'\b(?![\'"])'
                self.refactored_code = re.sub(pattern, new_name, self.refactored_code)
        
        elif "doesn't follow PascalCase" in message:
            # Extract original and suggested name
            match = re.search(r"'([^']+)' to '([^']+)'", issue['fix_suggestion'])
            if match:
                original_name = match.group(1)
                new_name = match.group(2)
                
                # Replace class definitions (more careful replacement)
                pattern = r'(class\s+)' + re.escape(original_name) + r'\b'
                self.refactored_code = re.sub(pattern, r'\1' + new_name, self.refactored_code)
    
    def _remove_unused_variables(self, issue):
        """Remove unused variable declarations."""
        match = re.search(r"'([^']+)'", issue['message'])
        if match:
            var_name = match.group(1)
            # Find assignments to this variable and remove them
            lines = self.refactored_code.split('\n')
            result_lines = []
            for line in lines:
                # Skip lines that only assign to this variable
                # But keep lines that do multiple things
                if re.match(rf'^\s*{re.escape(var_name)}\s*=', line) and ',' not in line:
                    continue
                result_lines.append(line)
            
            self.refactored_code = '\n'.join(result_lines)
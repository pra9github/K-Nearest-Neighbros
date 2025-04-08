from flask import Flask, render_template, request, jsonify
from code_analyzer import CodeAnalyzer, CodeRefactorer
from flask_socketio import SocketIO, emit
import time
import threading

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# Cache to store the last analysis results and reduce computational overhead
analysis_cache = {}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze_code():
    code = request.json.get('code', '')
    cursor_pos = request.json.get('cursor_pos', 0)
    current_line = request.json.get('current_line', '')
    
    analyzer = CodeAnalyzer(code)
    success = analyzer.parse()
    
    # Get code completions based on current context
    code_completions = analyzer.suggest_completion(current_line, cursor_pos)
    
    # If syntax error, provide syntax-specific suggestions
    if not success:
        return jsonify({
            'success': False,
            'syntax_error': True,
            'issues': analyzer.issues,
            'suggestions': [],
            'completions': code_completions
        })
    
    # Get all code quality issues and refactoring suggestions
    refactoring_suggestions = analyzer.suggest_refactoring()
    
    return jsonify({
        'success': True,
        'syntax_error': False,
        'suggestions': refactoring_suggestions,
        'completions': code_completions
    })

@app.route('/refactor', methods=['POST'])
def refactor_code():
    code = request.json.get('code', '')
    selected_issues = request.json.get('selected_issues', [])
    
    analyzer = CodeAnalyzer(code)
    success = analyzer.parse()
    
    if not success:
        return jsonify({
            'success': False,
            'issues': analyzer.issues,
            'refactored_code': code
        })
    
    refactorer = CodeRefactorer(code, selected_issues)
    refactored_code = refactorer.apply_refactorings()
    
    return jsonify({
        'success': True,
        'refactored_code': refactored_code
    })

@app.route('/auto_fix', methods=['POST'])
def auto_fix():
    code = request.json.get('code', '')
    issue_type = request.json.get('issue_type', '')
    
    analyzer = CodeAnalyzer(code)
    success = analyzer.parse()
    
    if not success and issue_type == 'syntax_error':
        # Try to fix the syntax error
        error = analyzer.syntax_error
        fixed_code = code
        
        if error:
            lines = code.split('\n')
            line_num = error['line'] - 1  # 0-indexed
            
            # Simple fixes for common syntax errors
            if "unexpected EOF" in error['msg'].lower():
                # Add missing closing bracket/parenthesis
                if ")" in error['msg']:
                    fixed_code += ")"
                elif "]" in error['msg']:
                    fixed_code += "]"
                elif "}" in error['msg']:
                    fixed_code += "}"
            elif "expected ':'" in error['msg'].lower():
                # Add missing colon
                if line_num < len(lines):
                    lines[line_num] = lines[line_num] + ":"
                    fixed_code = '\n'.join(lines)
            elif "IndentationError" in error['msg']:
                # Fix indentation
                if line_num < len(lines):
                    if "expected an indented block" in error['msg'].lower():
                        lines[line_num] = "    " + lines[line_num]
                    elif "unexpected indent" in error['msg'].lower():
                        lines[line_num] = lines[line_num].lstrip()
                    fixed_code = '\n'.join(lines)
        
        return jsonify({
            'success': True,
            'fixed_code': fixed_code
        })
    
    # Handle other specific issue types
    elif issue_type:
        # Find the specific issue
        issues = analyzer.suggest_refactoring()
        selected_issues = [issue for issue in issues if issue['type'] == issue_type]
        
        if selected_issues:
            refactorer = CodeRefactorer(code, selected_issues)
            fixed_code = refactorer.apply_refactorings()
            
            return jsonify({
                'success': True,
                'fixed_code': fixed_code
            })
    
    return jsonify({
        'success': False,
        'message': 'Could not auto-fix this issue',
        'fixed_code': code
    })

# New routes and socket handlers for real-time functionality

@socketio.on('connect')
def handle_connect():
    emit('connected', {'data': 'Connected to real-time code assistant'})

@socketio.on('code_change')
def handle_code_change(data):
    """Handle real-time code changes and provide immediate feedback."""
    code = data.get('code', '')
    cursor_pos = data.get('cursor_pos', 0)
    current_line = data.get('current_line', '')
    
    # Add caching to avoid unnecessary processing
    cache_key = f"{code}:{cursor_pos}:{current_line}"
    
    # Check if we've analyzed this exact state recently
    if cache_key in analysis_cache and time.time() - analysis_cache[cache_key]['timestamp'] < 5:
        emit('real_time_feedback', analysis_cache[cache_key]['result'])
        return
    
    # Analyze the code in a non-blocking way
    threading.Thread(target=analyze_and_emit, args=(code, cursor_pos, current_line, cache_key)).start()

def analyze_and_emit(code, cursor_pos, current_line, cache_key):
    """Perform analysis in a separate thread and emit results."""
    analyzer = CodeAnalyzer(code)
    success = analyzer.parse()
    
    # Get code completions based on current context
    code_completions = analyzer.suggest_completion(current_line, cursor_pos)
    
    # Get real-time syntax checking results
    if not success:
        result = {
            'success': False,
            'syntax_error': True,
            'issues': analyzer.issues,
            'line': analyzer.syntax_error['line'] if analyzer.syntax_error else None,
            'completions': code_completions
        }
    else:
        # For real-time feedback, let's focus on most important issues
        quick_suggestions = []
        
        # Get high-priority refactoring suggestions
        all_issues = analyzer.suggest_refactoring()
        
        # Filter to show only the most relevant ones in real-time
        for issue in all_issues:
            if issue['complexity'] == 'simple' or issue['type'] in ['undefined_variable', 'unused_imports']:
                quick_suggestions.append(issue)
        
        result = {
            'success': True,
            'syntax_error': False,
            'issues': quick_suggestions,
            'completions': code_completions[:5]  # Limit to top 5 completions for real-time
        }
    
    # Cache the results
    analysis_cache[cache_key] = {
        'timestamp': time.time(),
        'result': result
    }
    
    # Clean old cache entries
    clean_old_cache_entries()
    
    # Emit the results back to the client
    socketio.emit('real_time_feedback', result)

def clean_old_cache_entries():
    """Remove old entries from the cache."""
    current_time = time.time()
    keys_to_remove = []
    
    for key, value in analysis_cache.items():
        if current_time - value['timestamp'] > 60:  # Remove after 60 seconds
            keys_to_remove.append(key)
    
    for key in keys_to_remove:
        analysis_cache.pop(key, None)

@socketio.on('quick_fix_request')
def handle_quick_fix(data):
    """Handle real-time quick fix requests."""
    code = data.get('code', '')
    issue_type = data.get('issue_type', '')
    line_number = data.get('line_number', 0)
    
    analyzer = CodeAnalyzer(code)
    success = analyzer.parse()
    
    if not success and issue_type == 'syntax_error':
        # Try to fix the syntax error
        error = analyzer.syntax_error
        fixed_code = code
        
        if error:
            lines = code.split('\n')
            line_num = error['line'] - 1  # 0-indexed
            
            # Simple fixes for common syntax errors
            if "unexpected EOF" in error['msg'].lower():
                # Add missing closing bracket/parenthesis
                if ")" in error['msg']:
                    fixed_code += ")"
                elif "]" in error['msg']:
                    fixed_code += "]"
                elif "}" in error['msg']:
                    fixed_code += "}"
            elif "expected ':'" in error['msg'].lower():
                # Add missing colon
                if line_num < len(lines):
                    lines[line_num] = lines[line_num] + ":"
                    fixed_code = '\n'.join(lines)
            elif "IndentationError" in error['msg']:
                # Fix indentation
                if line_num < len(lines):
                    if "expected an indented block" in error['msg'].lower():
                        lines[line_num] = "    " + lines[line_num]
                    elif "unexpected indent" in error['msg'].lower():
                        lines[line_num] = lines[line_num].lstrip()
                    fixed_code = '\n'.join(lines)
        
        socketio.emit('quick_fix_result', {
            'success': True,
            'fixed_code': fixed_code
        })
        return
    
    # Handle other specific issue types
    elif issue_type:
        # Find the specific issue
        issues = analyzer.suggest_refactoring()
        selected_issues = [issue for issue in issues if issue['type'] == issue_type and 
                          (issue.get('line') is None or issue.get('line') == line_number)]
        
        if selected_issues:
            refactorer = CodeRefactorer(code, selected_issues)
            fixed_code = refactorer.apply_refactorings()
            
            socketio.emit('quick_fix_result', {
                'success': True,
                'fixed_code': fixed_code
            })
            return
    
    socketio.emit('quick_fix_result', {
        'success': False,
        'message': 'Could not auto-fix this issue',
        'fixed_code': code
    })

if __name__ == '__main__':
    socketio.run(app, debug=True)
import os
import json
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from groq import Groq
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from flask_dance.contrib.github import make_github_blueprint, github
from flask_dance.contrib.gitlab import make_gitlab_blueprint, gitlab
from typing import Dict, List, Any, Optional
import re
from modules.analyzer import analyze_code, complete_code, refactor_code

app = Flask(__name__)
app.secret_key = "1234"  # Replace with a strong key in production

# Define file paths
HISTORY_FILE = os.path.join(os.path.dirname(__file__), "data", "review_history.json")
USERS_FILE = os.path.join(os.path.dirname(__file__), "data", "users.json")
API_VERSION = "v1"

# Add timestamp_to_date filter to resolve the template error
@app.template_filter('timestamp_to_date')
def timestamp_to_date(timestamp):
    if timestamp:
        # Convert timestamp to datetime object and format it
        return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M')
    return ''

# History management functions
def load_history(user_id=None):
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            try:
                history = json.load(f)
                if user_id:
                    return [item for item in history if item.get("user_id") == user_id]
                return history
            except json.JSONDecodeError:
                return []
    return []

def save_history(history):
    # Ensure the directory exists
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)

def add_to_history(user_id, code, review, repo_provider=None, repo_name=None, file_path=None):
    history = load_history()
    history.append({
        "user_id": user_id,
        "code": code,
        "review": review,
        "timestamp": int(datetime.now().timestamp()),
        "repo_provider": repo_provider,
        "repo_name": repo_name,
        "file_path": file_path
    })
    save_history(history)

# User database functions
def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)

# OAuth setup for available providers
github_bp = make_github_blueprint(
    client_id=os.environ.get("GITHUB_CLIENT_ID", "Ov23liJax2oD04sMDcVn"),
    client_secret=os.environ.get("GITHUB_CLIENT_SECRET", "d58558f1186713797d54c1208f7c6108a0a0aac6"),
    scope="repo",
)
app.register_blueprint(github_bp, url_prefix="/login/github")

gitlab_bp = make_gitlab_blueprint(
    client_id=os.environ.get("GITLAB_CLIENT_ID", "your_gitlab_client_id"),
    client_secret=os.environ.get("GITLAB_CLIENT_SECRET", "your_gitlab_client_secret"),
    scope="api",
)
app.register_blueprint(gitlab_bp, url_prefix="/login/gitlab")

# Groq client setup
groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY", "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"))

# Repository provider handlers
repo_providers = {
    "github": github,
    "gitlab": gitlab
}

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# OAuth callback handlers
@app.route("/callback/<provider>")
def oauth_callback(provider):
    if provider not in repo_providers:
        return "Unsupported provider", 400
    
    provider_client = repo_providers[provider]
    
    if not provider_client.authorized:
        return redirect(url_for(f"{provider}.login"))
    
    if provider == "github":
        resp = provider_client.get("/user")
    elif provider == "gitlab":
        resp = provider_client.get("/api/v4/user")
    else:
        return "Unsupported provider", 400
        
    assert resp.ok, resp.text
    
    if provider == "github":
        username = resp.json()["login"]
    elif provider == "gitlab":
        username = resp.json()["username"]
    
    session["user_id"] = f"{provider}:{username}"
    session["provider"] = provider
    session["username"] = username
    
    return redirect(url_for("index"))

@app.route("/login_oauth")
def login_page():
    return render_template("login.html")

@app.route("/logout")
def logout():
    for provider in repo_providers:
        if f"{provider}_oauth_token" in session:
            del session[f"{provider}_oauth_token"]
    
    session.clear()
    return redirect(url_for("login"))

# Authentication routes
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form['username']
        password = request.form['password']
        users = load_users()
        
        if username in users and check_password_hash(users[username]['password'], password):
            session['username'] = username
            session['user_id'] = username  # Use username as user_id for regular login
            return redirect(url_for('index'))
        return render_template('login.html', error="Invalid username or password")
    
    return render_template('login.html')

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        if password != confirm_password:
            return render_template('register.html', error="Passwords don't match")
        
        users = load_users()
        if username in users:
            return render_template('register.html', error="Username already exists")
        
        users[username] = {
            'password': generate_password_hash(password)
        }
        save_users(users)
        
        session['username'] = username
        session['user_id'] = username  # Use username as user_id for regular login
        return redirect(url_for('index'))
    
    return render_template('register.html')

# Web UI routes
@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    review = ""
    repos = []
    
    provider = session.get("provider")
    
    if provider and provider in repo_providers and repo_providers[provider].authorized:
        # Fetch repositories for the authenticated user
        if provider == "github":
            repos_resp = github.get("/user/repos")
            if repos_resp.ok:
                repos = [{"name": repo["full_name"], "url": repo["html_url"]} for repo in repos_resp.json()]
        elif provider == "gitlab":
            repos_resp = gitlab.get("/api/v4/projects")
            if repos_resp.ok:
                repos = [{"name": repo["path_with_namespace"], "url": repo["web_url"]} for repo in repos_resp.json()]
    
    if request.method == "POST":
        code = request.form["code"]
        repo_name = request.form.get("repo_name", "")
        file_path = request.form.get("file_path", "")
        
        try:
            # Process code review
            analysis = analyze_code(code, groq_client)
            completion = complete_code(code, groq_client)
            refactor = refactor_code(code, groq_client)
            
            review = f"🔍 Analysis:\n{analysis}\n\n✨ Suggestions:\n{refactor}\n\n⚙️ Completion:\n{completion}"
            
            # Save review history
            add_to_history(
                user_id=session["user_id"],
                code=code,
                review=review,
                repo_provider=provider,
                repo_name=repo_name,
                file_path=file_path
            )
        except Exception as e:
            review = f"Error processing code: {str(e)}"
    
    return render_template("index.html", review=review, repos=repos, user=session.get("username"), provider=provider)

@app.route("/dashboard")
@login_required
def dashboard():
    history = load_history(user_id=session["user_id"])
    return render_template("dashboard.html", history=history, user=session.get("username"))

def calculate_acceptance_rate(suggestions):
    """Calculate acceptance rate for suggestions."""
    # For now, return a placeholder value
    # In a real implementation, you'd track which suggestions were actually applied
    return 50

# Helper functions for automated code generation
def detect_language(code, file_path=None):
    """Detect programming language based on code or file extension."""
    # Extract file extension if path is available
    if file_path:
        ext = file_path.split('.')[-1].lower()
        if ext in ['py', 'python']:
            return 'python'
        elif ext in ['js', 'javascript']:
            return 'javascript'
        elif ext in ['ts', 'typescript']:
            return 'typescript'
        elif ext in ['java']:
            return 'java'
        elif ext in ['rb', 'ruby']:
            return 'ruby'
        elif ext in ['go']:
            return 'go'
        elif ext in ['c', 'cpp', 'h', 'hpp']:
            return 'c++'
    
    # Fallback: analyze code patterns
    if re.search(r'import\s+[\w.]+|from\s+[\w.]+\s+import', code):
        return 'python'
    elif re.search(r'function\s+\w+\s*\(|const\s+\w+\s*=|let\s+\w+\s*=|var\s+\w+\s*=', code):
        return 'javascript'
    elif re.search(r'class\s+\w+|public\s+static\s+void', code):
        return 'java'
    
    return 'unknown'

def get_current_scope(code, cursor_position, language='unknown'):
    """Extract the current code scope (function, class, etc.)."""
    # Get code until cursor position
    code_until_cursor = code[:cursor_position]
    
    # Find the current function/method/class
    current_scope = {
        'type': None,
        'name': None,
        'content': '',
        'indentation': 0
    }
    
    if language == 'python':
        # Find the last def or class
        function_match = re.search(r'def\s+(\w+)\s*\([^)]*\)[^:]*:', code_until_cursor)
        class_match = re.search(r'class\s+(\w+)[^:]*:', code_until_cursor)
        
        if function_match:
            current_scope['type'] = 'function'
            current_scope['name'] = function_match.group(1)
        elif class_match:
            current_scope['type'] = 'class'
            current_scope['name'] = class_match.group(1)
    
    return current_scope

def generate_code_completions(code, cursor_position, ai_client, max_suggestions=3, file_path=None):
    """Generate code completion suggestions using AI."""
    if not ai_client:
        return []
    
    # Detect language
    language = detect_language(code, file_path)
    
    # Get current scope
    current_scope = get_current_scope(code, cursor_position, language)
    
    # Extract recent code (last few lines before cursor)
    lines = code[:cursor_position].split('\n')
    recent_code = '\n'.join(lines[-min(10, len(lines)):])
    
    # Prepare prompt for the AI
    prompt = f"""
Given the following {language} code, provide {max_suggestions} code completion suggestions.
The cursor is at the end of the code snippet.

CODE:
```{language}
{recent_code}
```

Current scope: {current_scope['type']} named {current_scope['name']} if detected.

Provide {max_suggestions} intelligent code completions that could follow this code.
Format as JSON with 'completions' containing a list of objects with 'code' and 'explanation' fields.
Each completion should be a coherent code snippet that logically follows the existing code.
"""
    
    try:
        # Call Groq API
        response = ai_client.chat.completions.create(
            model="mixtral-8x7b-32768",  # Adjust based on available models
            messages=[
                {"role": "system", "content": "You are a coding assistant specializing in code completion."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        
        # Extract and parse the result
        result = response.choices[0].message.content
        try:
            suggestions = json.loads(result).get('completions', [])
            return suggestions
        except json.JSONDecodeError:
            return [{"code": "# Error parsing AI response", "explanation": "Could not generate suggestions"}]
            
    except Exception as e:
        return [{"code": f"# Error: {str(e)}", "explanation": "Error generating suggestions"}]

# Routes for automated code analysis
@app.route("/automated")
@login_required
def automated():
    suggestions = load_history(user_id=session.get("user_id", ""))
    
    # Process suggestions for the template - simplified version
    processed_suggestions = []
    for suggestion in suggestions:
        # Only include if both code and review exist
        if suggestion.get("code") and suggestion.get("review"):
            processed_suggestions.append({
                "id": str(suggestions.index(suggestion)),
                "type": "analysis",  # Simplified to just one type
                "original_code": suggestion.get("code", ""),
                "suggested_code": suggestion.get("review", ""),
                "timestamp": suggestion.get("timestamp", 0)
            })
    
    # Convert to JSON for JavaScript
    suggestions_json = json.dumps(processed_suggestions)
    
    return render_template(
        "automated.html",
        user=session.get("username"),
        suggestions=processed_suggestions,
        suggestions_json=suggestions_json
    )

# API endpoints
@app.route(f"/api/{API_VERSION}/auth/status", methods=["GET"])
def auth_status():
    if "user_id" not in session:
        return jsonify({"authenticated": False})
    
    return jsonify({
        "authenticated": True,
        "user_id": session["user_id"],
        "provider": session.get("provider"),
        "username": session.get("username")
    })

@app.route(f"/api/{API_VERSION}/review", methods=["POST"])
def api_review():
    # Check authentication (using API token for IDE integrations)
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return jsonify({"error": "Unauthorized"}), 401
    
    token = auth_header.split(" ")[1]
    # TODO: Implement proper token validation
    
    data = request.json
    if not data or "code" not in data:
        return jsonify({"error": "Code is required"}), 400
    
    code = data["code"]
    repo_name = data.get("repo_name", "")
    file_path = data.get("file_path", "")
    user_id = data.get("user_id", "api_user")
    
    try:
        # Process code review
        analysis = analyze_code(code, groq_client)
        completion = complete_code(code, groq_client)
        refactor = refactor_code(code, groq_client)
        
        review = {
            "analysis": analysis,
            "suggestions": refactor,
            "completion": completion
        }
        
        # Save review history
        full_review = f"🔍 Analysis:\n{analysis}\n\n✨ Suggestions:\n{refactor}\n\n⚙️ Completion:\n{completion}"
        add_to_history(
            user_id=user_id,
            code=code,
            review=full_review,
            repo_provider=data.get("provider"),
            repo_name=repo_name,
            file_path=file_path
        )
        
        return jsonify({
            "success": True,
            "review": review
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route(f"/api/{API_VERSION}/history", methods=["GET"])
def api_history():
    # Check authentication
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return jsonify({"error": "Unauthorized"}), 401
    
    token = auth_header.split(" ")[1]
    # TODO: Implement proper token validation
    
    user_id = request.args.get("user_id", "")
    if not user_id:
        return jsonify({"error": "User ID is required"}), 400
    
    history = load_history(user_id=user_id)
    return jsonify({"history": history})

@app.route(f"/api/{API_VERSION}/ignore-suggestion", methods=["POST"])
def ignore_suggestion():
    """API endpoint to ignore a suggestion."""
    # For simplicity, we're not implementing full authentication here
    suggestion_id = request.json.get("suggestion_id")
    if not suggestion_id:
        return jsonify({"error": "Suggestion ID is required"}), 400
    
    # In a real implementation, you would update the suggestion status in the database
    return jsonify({"success": True})

@app.route("/autocomplete", methods=["POST"])
@login_required
def web_autocomplete():
    """Web endpoint for code autocompletion."""
    code = request.json.get("code", "")
    cursor_position = request.json.get("cursor_position", len(code))
    file_path = request.json.get("file_path", "")
    max_suggestions = request.json.get("max_suggestions", 3)
    
    try:
        # Generate code completions
        completions = generate_code_completions(
            code=code,
            cursor_position=cursor_position,
            ai_client=groq_client,
            max_suggestions=max_suggestions,
            file_path=file_path
        )
        
        language = detect_language(code, file_path)
        
        # Format the response for better display
        processed_completions = []
        for completion in completions:
            processed_completions.append({
                "code": completion["code"],
                "explanation": completion["explanation"],
                "language": language
            })
        
        # Save to history with more detailed information
        if session.get("user_id"):
            add_to_history(
                user_id=session["user_id"],
                code=code,
                review=json.dumps(processed_completions),
                repo_provider=session.get("provider"),
                repo_name=request.json.get("repo_name", ""),
                file_path=file_path
            )
        
        return jsonify({
            "success": True,
            "language": language,
            "completions": processed_completions
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

# Create data directory and files at startup
if __name__ == "__main__":
    # Create data directory
    os.makedirs(os.path.join(os.path.dirname(__file__), "data"), exist_ok=True)
    
    # Initialize files if they don't exist
    if not os.path.exists(HISTORY_FILE):
        save_history([])
    if not os.path.exists(USERS_FILE):
        save_users({})
    
    app.run(debug=True)
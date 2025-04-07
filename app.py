import os
import json
from flask import Flask, render_template, request, redirect, url_for
from groq import Groq  # Make sure to `pip install groq`

from modules.analyzer import analyze_code, complete_code, refactor_code

app = Flask(__name__)

# Groq client setup
groq_client = Groq(api_key="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")  # replace with your actual Groq API key

HISTORY_FILE = "review_history.json"

# Load review history from file
def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            return json.load(f)
    return []

# Save review history to file
def save_history(history):
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)

@app.route("/", methods=["GET", "POST"])
def index():
    review = ""
    if request.method == "POST":
        code = request.form["code"]

        # Analyze, complete, and refactor the code
        analysis = analyze_code(code, groq_client)
        completion = complete_code(code, groq_client)
        refactor = refactor_code(code, groq_client)

        # Combine all reviews
        review = f"🔍 Analysis:\n{analysis}\n\n✨ Suggestions:\n{refactor}\n\n⚙️ Completion:\n{completion}"

        # Save review history
        history = load_history()
        history.append({"code": code, "review": review})
        save_history(history)

    return render_template("index.html", review=review)

@app.route("/dashboard")
def dashboard():
    history = load_history()
    return render_template("dashboard.html", history=history)

if __name__ == "__main__":
    app.run(debug=True)

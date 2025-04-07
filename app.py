from flask import Flask, render_template, request
from dotenv import load_dotenv
import os
import groq

# Load environment variables from .env
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# Initialize Groq client with API key
client = groq.Groq(api_key=os.getenv("GROQ_API_KEY"))

# Function to send code to Groq LLM and get review
def get_code_review(code):
    prompt = f"""You are a code review assistant. Analyze the following code and identify:
1. Security vulnerabilities
2. Performance issues
3. Code quality improvements
Return your feedback in bullet points.

Code:
{code}
"""
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",  # Updated model
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2
    )
    return response.choices[0].message.content

# Main route
@app.route("/", methods=["GET", "POST"])
def index():
    review = ""
    if request.method == "POST":
        code = request.form.get("code")
        if code:
            review = get_code_review(code)
    return render_template("index.html", review=review)

# Run the app
if __name__ == "__main__":
    app.run(debug=True)

def analyze_code(code, client):
    prompt = f"Review this code for bugs, security issues, and optimizations:\n\n{code}"
    response = client.chat.completions.create(
        model="llama3-70b-8192",
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content.strip()

def complete_code(code, client):
    prompt = f"Complete the following code:\n\n{code}"
    response = client.chat.completions.create(
        model="llama3-70b-8192",
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content.strip()

def refactor_code(code, client):
    prompt = f"Suggest refactoring techniques for better maintainability and readability:\n\n{code}"
    response = client.chat.completions.create(
        model="llama3-70b-8192",
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content.strip()

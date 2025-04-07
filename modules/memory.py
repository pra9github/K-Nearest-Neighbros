import os
import json

HISTORY_FILE = 'review_history.json'

def save_review(code, review):
    history = get_previous_reviews()
    history.append({"code": code, "review": review})
    with open(HISTORY_FILE, 'w') as f:
        json.dump(history, f)

def get_previous_reviews():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r') as f:
            return json.load(f)
    return []

import os
from flask import Flask, request, jsonify
import requests
import json

app = Flask(__name__)

# Freshdesk API configuration (move to environment variables for security)
FRESHDESK_DOMAIN = os.getenv("FRESHDESK_DOMAIN", "netcomafricateam.freshdesk.com")
API_KEY = os.getenv("FRESHDESK_API_KEY", "AdvS0xFIQqoinv5tQEqJZQ")

@app.route('/webhook', methods=['POST'])
def handle_webhook():
    try:
        payload = request.get_json()
        if not payload:
            return jsonify({"error": "No payload provided"}), 400

        ticket_id = payload.get("ticket_id")
        reply_id = payload.get("conversation_id")
        event = payload.get("event")

        if not ticket_id or not reply_id or event != "reply_sent":
            return jsonify({"error": "Invalid payload"}), 400

        ticket_url = f"https://{FRESHDESK_DOMAIN}/api/v2/tickets/{ticket_id}"
        headers = {"Authorization": f"Basic {API_KEY}"}
        response = requests.get(ticket_url, headers=headers)
        if response.status_code != 200:
            return jsonify({"error": f"Failed to fetch ticket {ticket_id}: {response.text}"}), 500

        ticket_data = response.json()
        parent_ticket_id = ticket_data.get("custom_fields", {}).get("parent_ticket_id")

        if not parent_ticket_id:
            return jsonify({"error": f"No parent ticket ID found for ticket {ticket_id}"}), 400

        conversations_url = f"https://{FRESHDESK_DOMAIN}/api/v2/tickets/{ticket_id}/conversations"
        response = requests.get(conversations_url, headers=headers)
        if response.status_code != 200:
            return jsonify({"error": f"Failed to fetch conversations for ticket {ticket_id}: {response.text}"}), 500

        conversations = response.json()
        latest_reply = None
        for convo in conversations:
            if convo["id"] == reply_id and convo["source"] == 2:
                latest_reply = convo["body_text"]
                break

        if not latest_reply:
            return jsonify({"error": f"No matching reply found for conversation ID {reply_id}"}), 404

        note_url = f"https://{FRESHDESK_DOMAIN}/api/v2/tickets/{parent_ticket_id}/notes"
        note_data = {
            "body": f"New reply from child ticket #{ticket_id}:\n{latest_reply}",
            "private": True
        }
        response = requests.post(note_url, headers=headers, json=note_data)
        if response.status_code == 201:
            return jsonify({"message": f"Successfully added note to parent ticket #{parent_ticket_id}"}), 200
        else:
            return jsonify({"error": f"Failed to add note to parent ticket #{parent_ticket_id}: {response.text}"}), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))

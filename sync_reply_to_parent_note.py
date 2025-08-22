# sync_reply_to_parent_note.py
import os
from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

# Freshdesk API configuration (moved to environment variables)
FRESHDESK_DOMAIN = os.getenv("FRESHDESK_DOMAIN")
FRESHDESK_API_KEY = os.getenv("FRESHDESK_API_KEY")

if not FRESHDESK_API_KEY or not FRESHDESK_DOMAIN:
    print("WARNING: Freshdesk API Key or Domain not set. This will fail on deployment.")

@app.route('/webhook', methods=['POST'])
def handle_webhook():
    try:
        # 1. Receive the full ticket payload from the webhook
        # Freshdesk's webhook sends the whole ticket object
        payload = request.get_json()
        if not payload or 'ticket' not in payload:
            return jsonify({"error": "Invalid webhook payload. 'ticket' object is missing."}), 400

        ticket_data = payload.get('ticket')
        
        # 2. Get the parent ticket ID directly from the webhook payload
        # It's usually a custom field, so the exact name may vary.
        # This assumes your custom field is named 'cf_parent_ticket_id'
        parent_ticket_id = ticket_data.get('cf_parent_ticket_id')

        # A more generic way to get it from the standard Freshdesk "association type"
        # relation_type = ticket_data.get('association_type')
        # parent_ticket_id = ticket_data.get('parent_id')
        
        # We will stick to the cf_ approach since you likely set a custom field
        if not parent_ticket_id:
            return jsonify({"message": "Not a child ticket, or parent ID is missing."}), 200

        # 3. Get the content of the latest thread update from the payload
        # This is far more efficient than making extra API calls
        latest_reply = payload.get('latest_public_comment')
        latest_note = payload.get('latest_note')

        if latest_reply and 'body_text' in latest_reply:
            thread_content = latest_reply['body_text']
            source = "Reply"
        elif latest_note and 'body_text' in latest_note:
            thread_content = latest_note['body_text']
            source = "Note"
        else:
            return jsonify({"message": "No new reply or note found in the payload."}), 200

        # 4. Use Freshdesk API to add a note to the parent ticket
        api_url = f"https://{FRESHDESK_DOMAIN}/api/v2/tickets/{parent_ticket_id}/notes"
        
        note_data = {
            "body": f"--- {source} from Child Ticket #{ticket_data['id']} ---\n{thread_content}",
            "private": True
        }
        
        headers = {
            "Content-Type": "application/json"
        }
        auth = (FRESHDESK_API_KEY, 'X') # Correct Freshdesk API key auth format

        response = requests.post(api_url, headers=headers, json=note_data, auth=auth)

        if response.status_code == 201:
            return jsonify({"message": f"Successfully added note to parent ticket #{parent_ticket_id}"}), 200
        else:
            return jsonify({"error": f"Failed to add note: {response.text}"}), 500

    except Exception as e:
        print(f"An error occurred: {e}")
        return jsonify({"error": "An internal server error occurred", "details": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))

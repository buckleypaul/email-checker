Use the gmail MCP tool to fetch my new emails using get_new_emails.

Analyze each email and return ONLY a JSON array (no markdown, no explanation) of emails I should respond to. Include emails that:
- Are from coworkers or collaborators about active work
- Require a decision or action from me
- Are time-sensitive (deadlines, meetings, urgent requests)

Do NOT include:
- Newsletters or marketing
- Automated notifications or alerts
- Receipts or confirmations

Each item in the array should have:
{
  "id": "gmail message id",
  "subject": "email subject",
  "from": "Sender Name <email@example.com>",
  "snippet": "1-2 sentence summary of what the email is about",
  "reason": "brief reason why I should respond"
}

If there are no emails to respond to, return an empty JSON array: []

from botbuilder.schema import Attachment, CardAction, ActionTypes
from typing import List, Dict, Any


def create_question_card(
    participant_name: str,
    question: str,
    tasks: List[Dict[str, Any]]
) -> Attachment:
    """Create an Adaptive Card for standup questions."""
    task_items = []
    for t in tasks:
        icon = "✅" if t["status"] == "DONE" else "🔴" if t["status"] == "BLOCKED" else "🔵"
        task_items.append({
            "type": "ColumnSet",
            "columns": [
                {"type": "Column", "width": "auto", "items": [
                    {"type": "TextBlock", "text": icon, "size": "Medium"}
                ]},
                {"type": "Column", "width": "stretch", "items": [
                    {"type": "TextBlock", "text": t["title"], "wrap": True, "size": "Small"}
                ]}
            ]
        })

    card = {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.4",
        "body": [
            {"type": "TextBlock", "text": f"Hey {participant_name}! 👋", "weight": "Bolder", "size": "Medium"},
            {"type": "TextBlock", "text": "Your current tasks:", "weight": "Bolder", "size": "Small", "spacing": "Medium"},
            *task_items,
            {"type": "TextBlock", "text": question, "wrap": True, "spacing": "Large", "weight": "Bolder"},
            {
                "type": "ActionSet",
                "actions": [
                    {"type": "Action.Submit", "title": "✅ On Track", "data": {"quickReply": "on_track"}},
                    {"type": "Action.Submit", "title": "🔴 Blocked", "data": {"quickReply": "blocked"}},
                    {"type": "Action.Submit", "title": "💬 Type Response", "data": {"quickReply": "custom"}}
                ]
            }
        ]
    }

    return Attachment(
        content_type="application/vnd.microsoft.card.adaptive",
        content=card
    )


def create_summary_card(summary: str, blockers: List[str], action_items: List[str]) -> Attachment:
    """Create an Adaptive Card for meeting summary."""
    body = [
        {"type": "TextBlock", "text": "📋 Standup Summary", "weight": "Bolder", "size": "Large"},
        {"type": "TextBlock", "text": summary, "wrap": True, "spacing": "Medium"},
    ]

    if blockers:
        body.append({"type": "TextBlock", "text": "🚨 Blockers", "weight": "Bolder", "color": "Attention", "spacing": "Large"})
        for b in blockers:
            body.append({"type": "TextBlock", "text": f"• {b}", "wrap": True, "color": "Attention"})

    if action_items:
        body.append({"type": "TextBlock", "text": "✅ Action Items", "weight": "Bolder", "color": "Good", "spacing": "Large"})
        for a in action_items:
            body.append({"type": "TextBlock", "text": f"• {a}", "wrap": True})

    card = {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.4",
        "body": body
    }

    return Attachment(
        content_type="application/vnd.microsoft.card.adaptive",
        content=card
    )

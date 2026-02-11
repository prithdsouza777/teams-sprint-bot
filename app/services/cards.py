from botbuilder.schema import Attachment, CardAction, ActionTypes, AudioCard, MediaUrl
from typing import List, Dict, Any


def create_audio_card(text: str, audio_url: str) -> Attachment:
    """Create an AudioCard to accompany text."""
    card = AudioCard(
        title="AI Voice Assistant",
        subtitle="Click play to listen",
        text=text,
        media=[MediaUrl(url=audio_url)],
        autoloop=False,
        autostart=False
    )
    return Attachment(
        content_type="application/vnd.microsoft.card.audio",
        content=card
    )


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
                    {"type": "Action.Submit", "title": "🔴 Blocked", "data": {"quickReply": "blocked"}}
                ]
            },
            {"type": "TextBlock", "text": "Or just type your response below 👇", "size": "Small", "isSubtle": True, "horizontalAlignment": "Center"}
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


def create_scrum_master_menu_card(user_name: str) -> Attachment:
    """Create a menu card for Scrum Masters with extra options."""
    card = {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.4",
        "body": [
            {"type": "TextBlock", "text": f"👋 Hi {user_name}!", "weight": "Bolder", "size": "Large"},
            {"type": "TextBlock", "text": "As a **Scrum Master**, you have access to:", "wrap": True},
            {"type": "TextBlock", "text": "• Start your daily standup\n• Assign tasks to team members", "wrap": True, "spacing": "Small"}
        ],
        "actions": [
            {"type": "Action.Submit", "title": "🎯 Start Standup", "data": {"action": "start_standup"}},
            {"type": "Action.Submit", "title": "📋 Assign Task", "data": {"action": "assign_task"}}
        ]
    }

    return Attachment(
        content_type="application/vnd.microsoft.card.adaptive",
        content=card
    )


def create_task_assignment_prompt_card() -> Attachment:
    """Create a card prompting the Scrum Master to describe the task assignment."""
    card = {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.4",
        "body": [
            {"type": "TextBlock", "text": "📋 Assign a Task", "weight": "Bolder", "size": "Large"},
            {"type": "TextBlock", "text": "Describe the task in natural language. For example:", "wrap": True},
            {"type": "TextBlock", "text": "• \"Give John the task to fix the login bug\"\n• \"Assign the homepage redesign to Sarah\"\n• \"Mukund needs to review the API documentation\"", "wrap": True, "size": "Small", "isSubtle": True},
            {
                "type": "Input.Text",
                "id": "taskDescription",
                "placeholder": "Describe the task assignment...",
                "isMultiline": True
            }
        ],
        "actions": [
            {"type": "Action.Submit", "title": "✅ Assign Task", "data": {"action": "submit_task_assignment"}},
            {"type": "Action.Submit", "title": "❌ Cancel", "data": {"action": "cancel_assignment"}}
        ]
    }

    return Attachment(
        content_type="application/vnd.microsoft.card.adaptive",
        content=card
    )


def create_task_assignment_confirmation_card(assignee: str, task_title: str, assigned_by: str) -> Attachment:
    """Create a confirmation card after task assignment."""
    card = {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.4",
        "body": [
            {"type": "TextBlock", "text": "✅ Task Assigned!", "weight": "Bolder", "size": "Large", "color": "Good"},
            {"type": "FactSet", "facts": [
                {"title": "Task", "value": task_title},
                {"title": "Assigned to", "value": assignee},
                {"title": "Assigned by", "value": assigned_by}
            ]},
            {"type": "TextBlock", "text": f"{assignee} will be notified when they start their next standup.", "wrap": True, "isSubtle": True, "spacing": "Medium"}
        ]
    }

    return Attachment(
        content_type="application/vnd.microsoft.card.adaptive",
        content=card
    )


def create_new_tasks_notification_card(tasks: List[Dict[str, Any]]) -> Attachment:
    """Create a card notifying user of newly assigned tasks."""
    task_items = []
    for t in tasks:
        task_items.append({
            "type": "ColumnSet",
            "columns": [
                {"type": "Column", "width": "auto", "items": [
                    {"type": "TextBlock", "text": "📋", "size": "Medium"}
                ]},
                {"type": "Column", "width": "stretch", "items": [
                    {"type": "TextBlock", "text": t.get("title", "Task"), "wrap": True, "weight": "Bolder"},
                    {"type": "TextBlock", "text": f"Assigned by: {t.get('assigned_by', 'Unknown')}", "size": "Small", "isSubtle": True}
                ]}
            ]
        })

    card = {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.4",
        "body": [
            {"type": "TextBlock", "text": "🆕 New Tasks Assigned to You!", "weight": "Bolder", "size": "Medium", "color": "Accent"},
            *task_items,
            {"type": "TextBlock", "text": "These have been added to your TODO list.", "spacing": "Medium", "isSubtle": True}
        ]
    }

    return Attachment(
        content_type="application/vnd.microsoft.card.adaptive",
        content=card
    )


def create_completed_menu_card(user_name: str, action_taken: str) -> Attachment:
    """Create a read-only version of the Scrum Master menu after an action is taken."""
    card = {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.4",
        "body": [
            {"type": "TextBlock", "text": f"👋 Hi {user_name}!", "weight": "Bolder", "size": "Large"},
            {"type": "TextBlock", "text": f"✅ Selected: **{action_taken}**", "wrap": True, "color": "Good"}
        ]
    }
    return Attachment(
        content_type="application/vnd.microsoft.card.adaptive",
        content=card
    )


def create_completed_task_prompt_card(action_taken: str) -> Attachment:
    """Create a read-only version of the task assignment prompt after action."""
    card = {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.4",
        "body": [
            {"type": "TextBlock", "text": "📋 Assign a Task", "weight": "Bolder", "size": "Large"},
            {"type": "TextBlock", "text": f"✅ {action_taken}", "wrap": True, "color": "Good"}
        ]
    }
    return Attachment(
        content_type="application/vnd.microsoft.card.adaptive",
        content=card
    )


def create_completed_question_card(
    participant_name: str,
    question: str,
    response_chosen: str,
    tasks: List[Dict[str, Any]]
) -> Attachment:
    """Create a read-only version of the standup question card after response."""
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
            {"type": "TextBlock", "text": f"✅ Response: {response_chosen}", "wrap": True, "color": "Good", "spacing": "Medium"}
        ]
    }
    return Attachment(
        content_type="application/vnd.microsoft.card.adaptive",
        content=card
    )

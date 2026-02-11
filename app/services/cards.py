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
                    {
                        "type": "Action.Execute",
                        "title": "✅ On Track",
                        "verb": "submit_standup_answer",
                        "data": {"quickReply": "on_track"}
                    },
                    {
                        "type": "Action.Execute",
                        "title": "🔴 Blocked",
                        "verb": "submit_standup_answer",
                        "data": {"quickReply": "blocked"}
                    }
                ]
            },
            {"type": "TextBlock", "text": "Or just type your response below 👇", "size": "Small", "isSubtle": True, "horizontalAlignment": "Center"}
        ]
    }

    return Attachment(
        content_type="application/vnd.microsoft.card.adaptive",
        content=card
    )


def create_simple_message_card(text: str) -> Attachment:
    """Create a simple card with a text message (for updates)."""
    card = {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.4",
        "body": [
            {"type": "TextBlock", "text": text, "wrap": True}
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


def create_scrum_master_menu_card(scrum_master_name: str) -> Attachment:
    """Create a menu card for Scrum Master."""
    card = {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.4",
        "body": [
            {"type": "TextBlock", "text": f"Scrum Master Menu ({scrum_master_name})", "weight": "Bolder", "size": "Medium"},
            {"type": "TextBlock", "text": "What would you like to do?", "isSubtle": True, "spacing": "Small"},
            {
                "type": "ActionSet",
                "actions": [
                    {
                        "type": "Action.Execute",
                        "title": "🚀 Start Standup",
                        "verb": "start_standup",
                        "data": {"action": "start_standup"}
                    },
                    {
                        "type": "Action.Execute",
                        "title": "📋 Assign Task",
                        "verb": "assign_task",
                        "data": {"action": "assign_task"}
                    }
                ]
            }
        ]
    }
    return Attachment(
        content_type="application/vnd.microsoft.card.adaptive",
        content=card
    )


def create_task_assignment_prompt_card() -> Attachment:
    """Create a card to prompt for task assignment details."""
    card = {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.4",
        "body": [
            {"type": "TextBlock", "text": "📋 Assign a New Task", "weight": "Bolder", "size": "Medium"},
            {"type": "TextBlock", "text": "Describe the task and who it's for:", "wrap": True},
            {
                "type": "Input.Text",
                "id": "taskDescription",
                "placeholder": "e.g., 'Assign the API docs to John'",
                "isMultiline": True
            },
            {
                "type": "ActionSet",
                "actions": [
                    {
                        "type": "Action.Execute",
                        "title": "Submit Assignment",
                        "verb": "submit_task_assignment",
                        "data": {"action": "submit_task_assignment"}
                    },
                    {
                        "type": "Action.Execute",
                        "title": "Cancel",
                        "verb": "cancel_assignment",
                        "data": {"action": "cancel_assignment"}
                    }
                ]
            }
        ]
    }
    return Attachment(
        content_type="application/vnd.microsoft.card.adaptive",
        content=card
    )


def create_task_assignment_confirmation_card(assignee: str, task_title: str, assigned_by: str) -> Attachment:
    """Create a confirmation card for task assignment."""
    card = {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.4",
        "body": [
            {"type": "TextBlock", "text": "✅ Task Assigned!", "weight": "Bolder", "size": "Medium", "color": "Good"},
            {"type": "FactSet", "facts": [
                {"title": "Task:", "value": task_title},
                {"title": "Assignee:", "value": assignee},
                {"title": "Assigned By:", "value": assigned_by}
            ]}
        ]
    }
    return Attachment(
        content_type="application/vnd.microsoft.card.adaptive",
        content=card
    )


def create_new_tasks_notification_card(tasks: List[Dict[str, Any]]) -> Attachment:
    """Create a notification card for new tasks."""
    task_facts = [{"title": "•", "value": t["title"]} for t in tasks]
    
    card = {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.4",
        "body": [
            {"type": "TextBlock", "text": "🔔 You have new tasks!", "weight": "Bolder", "size": "Medium", "color": "Accent"},
            {"type": "FactSet", "facts": task_facts},
            {"type": "TextBlock", "text": "These have been added to your backlog.", "isSubtle": True, "size": "Small", "spacing": "Small"}
        ]
    }
    return Attachment(
        content_type="application/vnd.microsoft.card.adaptive",
        content=card
    )




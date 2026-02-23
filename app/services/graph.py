"""
Microsoft Graph API Client.

Creates Teams online meetings and resolves user Entra Object IDs.
Used for voice standup: create meeting -> get joinWebUrl -> ACS joins it.
"""

from loguru import logger
from typing import Optional, Dict, Any

from app.config import settings

_graph_client = None


def _get_graph_client():
    """Lazy-initialize the Graph SDK client using bot's app credentials."""
    global _graph_client
    if _graph_client is not None:
        return _graph_client

    if not settings.MICROSOFT_APP_ID or not settings.MICROSOFT_APP_PASSWORD:
        logger.warning("MICROSOFT_APP_ID/PASSWORD not set — Graph API disabled")
        return None

    if not settings.MICROSOFT_TENANT_ID:
        logger.warning("MICROSOFT_TENANT_ID not set — Graph API disabled")
        return None

    try:
        from azure.identity import ClientSecretCredential
        from msgraph import GraphServiceClient

        credential = ClientSecretCredential(
            tenant_id=settings.MICROSOFT_TENANT_ID,
            client_id=settings.MICROSOFT_APP_ID,
            client_secret=settings.MICROSOFT_APP_PASSWORD,
        )
        _graph_client = GraphServiceClient(
            credential,
            scopes=["https://graph.microsoft.com/.default"],
        )
        logger.info("Graph SDK client initialized")
        return _graph_client
    except ImportError:
        logger.warning("msgraph-sdk not installed — Graph API disabled")
        return None
    except Exception as e:
        logger.error(f"Failed to init Graph client: {e}")
        return None


async def create_online_meeting(
    organizer_oid: str,
    subject: str = "Daily Standup",
    participant_oids: Optional[list[str]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Create a Teams online meeting via Graph API.

    Args:
        organizer_oid: Entra Object ID of the meeting organizer.
        subject: Meeting subject line.
        participant_oids: Optional list of Entra OIDs to invite.

    Returns:
        {"meeting_id": str, "join_web_url": str} or None on failure.
    """
    client = _get_graph_client()
    if client is None:
        logger.error(
            "Graph client is None — check MICROSOFT_APP_ID, MICROSOFT_APP_PASSWORD, "
            "MICROSOFT_TENANT_ID in .env and that msgraph-sdk is installed"
        )
        return None

    logger.info(
        f"Creating online meeting: organizer_oid={organizer_oid}, "
        f"subject={subject}, participants={len(participant_oids or [])}"
    )

    try:
        from msgraph.generated.models.online_meeting import OnlineMeeting
        from msgraph.generated.models.lobby_bypass_settings import LobbyBypassSettings
        from msgraph.generated.models.lobby_bypass_scope import LobbyBypassScope
        from msgraph.generated.models.meeting_participants import MeetingParticipants
        from msgraph.generated.models.meeting_participant_info import MeetingParticipantInfo
        from msgraph.generated.models.identity_set import IdentitySet
        from msgraph.generated.models.identity import Identity

        request_body = OnlineMeeting(
            subject=subject,
            lobby_bypass_settings=LobbyBypassSettings(
                scope=LobbyBypassScope.Everyone,
            ),
        )

        # Add participants if provided
        if participant_oids:
            attendees = []
            for oid in participant_oids:
                attendees.append(
                    MeetingParticipantInfo(
                        identity=IdentitySet(
                            user=Identity(id=oid),
                        ),
                    )
                )
            request_body.participants = MeetingParticipants(
                attendees=attendees,
            )

        result = await client.users.by_user_id(organizer_oid).online_meetings.post(
            request_body
        )

        if result and result.join_web_url:
            logger.info(f"Meeting created: {result.id}")
            return {
                "meeting_id": result.id,
                "join_web_url": result.join_web_url,
            }

        logger.error("Meeting creation returned no join URL")
        return None

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Failed to create online meeting: {error_msg}")

        # Log common causes for easier debugging
        if "Authorization" in error_msg or "403" in error_msg:
            logger.error(
                "403 Forbidden — likely missing OnlineMeetings.ReadWrite.All permission "
                "or admin consent not granted"
            )
        elif "404" in error_msg:
            logger.error(
                f"404 Not Found — organizer_oid '{organizer_oid}' may not be a valid "
                "user in the tenant, or user has no Teams license"
            )
        elif "401" in error_msg:
            logger.error(
                "401 Unauthorized — client credentials may be wrong, or tenant ID mismatch"
            )

        return None


async def get_user_oid_by_email(email: str) -> Optional[Dict[str, str]]:
    """
    Resolve a user's Entra Object ID from their email/UPN.

    Returns:
        {"entra_oid": str, "display_name": str} or None.
    """
    client = _get_graph_client()
    if client is None:
        return None

    try:
        result = await client.users.by_user_id(email).get()
        if result and result.id:
            return {
                "entra_oid": result.id,
                "display_name": result.display_name or email,
            }
        return None
    except Exception as e:
        logger.warning(f"Could not resolve user by email {email}: {e}")
        return None


async def get_user_oid_by_name(display_name: str) -> Optional[Dict[str, str]]:
    """
    Search for a user by display name in Azure AD.

    Returns:
        {"entra_oid": str, "display_name": str, "email": str} or None.
    """
    client = _get_graph_client()
    if client is None:
        return None

    try:
        from msgraph.generated.users.users_request_builder import UsersRequestBuilder

        query_params = UsersRequestBuilder.UsersRequestBuilderGetQueryParameters(
            filter=f"displayName eq '{display_name}'",
            top=1,
        )
        config = UsersRequestBuilder.UsersRequestBuilderGetRequestConfiguration(
            query_parameters=query_params,
        )
        result = await client.users.get(request_configuration=config)

        if result and result.value and len(result.value) > 0:
            user = result.value[0]
            return {
                "entra_oid": user.id,
                "display_name": user.display_name or display_name,
                "email": user.user_principal_name or "",
            }
        return None
    except Exception as e:
        logger.warning(f"Could not resolve user by name '{display_name}': {e}")
        return None

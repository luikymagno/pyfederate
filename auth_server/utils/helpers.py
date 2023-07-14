from typing import Annotated, Awaitable, Callable, Dict
from fastapi import status, Query, Path

from ..utils import constants, telemetry, schemas, exceptions
from .constants import GrantType
from ..auth_manager import manager as auth_manager

logger = telemetry.get_logger(__name__)

######################################## Dependency Functions ########################################

async def get_client(
        client_id: Annotated[
            str,
            Query(min_length=constants.CLIENT_ID_MIN_LENGH, max_length=constants.CLIENT_ID_MAX_LENGH)
        ]
) -> schemas.Client:
    
    try:
        client: schemas.Client = await auth_manager.client_manager.get_client(client_id=client_id)
    except exceptions.ClientDoesNotExist:
        logger.info(f"The client with ID: {client_id} does not exists")
        raise exceptions.HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            error=constants.ErrorCode.INVALID_CLIENT,
            error_description="invalid credentials"
        )
    
    return client

async def get_authenticated_client(
        client_id: Annotated[
            str,
            Query(min_length=constants.CLIENT_ID_MIN_LENGH, max_length=constants.CLIENT_ID_MAX_LENGH)
        ],
        client_secret: Annotated[
            str,
            Query(max_length=constants.CLIENT_SECRET_MIN_LENGH, min_length=constants.CLIENT_SECRET_MAX_LENGH)
        ]       
) -> schemas.Client:
    
    client: schemas.Client = await get_client(client_id=client_id)

    if(not client.is_authenticated(client_secret=client_secret)):
        logger.info(f"The client with ID: {client_id} is not authenticated")
        raise exceptions.HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            error=constants.ErrorCode.INVALID_CLIENT,
            error_description="invalid credentials"
        )
    
    return client

async def setup_session_by_callback_id(
    callback_id: Annotated[str, Path(min_length=constants.CALLBACK_ID_LENGTH, max_length=constants.CALLBACK_ID_LENGTH)]
) -> schemas.SessionInfo:
    """
    Fetch the session associated to the callback_id if it exists and
    set the tracking and correlation IDs using the session information
    """
    
    try:
        session: schemas.SessionInfo = await auth_manager.session_manager.get_session_by_callback_id(callback_id=callback_id)
    except exceptions.SessionInfoDoesNotExist:
        logger.info(f"The callback ID: {callback_id} has no session associated with it")
        raise exceptions.HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            error=constants.ErrorCode.INVALID_REQUEST,
            error_description="Invalid callback ID"
        )
    
    # Overwrite the telemetry IDs set by default with the ones from the session
    telemetry.tracking_id.set(session.tracking_id)
    telemetry.correlation_id.set(session.correlation_id)
    return session

######################################## Grant Handlers ########################################

#################### Client Credentials ####################

async def client_credentials_token_handler(
    grant_context: schemas.GrantContext
) -> schemas.TokenResponse:
    
    client: schemas.Client = grant_context.client
    # Check if the scopes requested are available to the client
    if(not client.are_scopes_allowed(requested_scopes=grant_context.requested_scopes)):
        raise exceptions.HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            error=constants.ErrorCode.INVALID_SCOPE,
            error_description="the client does not have access to the required scopes"
        )

    token_model: schemas.TokenModel = client.token_model
    token: schemas.BearerToken = token_model.generate_token(
        client_id=client.id,
        subject=client.id,
        # If the client didn't inform any scopes, send all the available ones
        scopes=grant_context.requested_scopes if grant_context.requested_scopes else client.scopes
    )
    return schemas.TokenResponse(
        access_token=token.token,
        expires_in=token_model.expires_in
    )

#################### Authorization Code ####################

async def authorization_code_token_handler(
    grant_context: schemas.GrantContext
) -> schemas.TokenResponse:
    
    if(grant_context.auth_code is None):
        raise exceptions.HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            error=constants.ErrorCode.INVALID_GRANT,
            error_description="the authorization code cannot be null for the authorization_code grant"
        )

    session: schemas.SessionInfo = await auth_manager.session_manager.get_session_by_auth_code(
        auth_code=grant_context.auth_code
    )
    client: schemas.Client = grant_context.client

    # Ensure the client is the same one defined in the session
    if(client.id != session.client_id):
        raise exceptions.HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            error=constants.ErrorCode.INVALID_REQUEST,
            error_description="invalid authorization code"
        )
    # Check if the scopes requested are available to the client
    if(not client.are_scopes_allowed(requested_scopes=session.requested_scopes)):
        raise exceptions.HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            error=constants.ErrorCode.INVALID_SCOPE,
            error_description="the client does not have access to the required scopes"
        )

    token_model: schemas.TokenModel = client.token_model
    token: schemas.BearerToken = token_model.generate_token(
        client_id=client.id,
        subject=client.id,
        scopes=session.requested_scopes
    )
    return schemas.TokenResponse(
        access_token=token.token,
        expires_in=token_model.expires_in
    )

#################### Handler Object ####################

grant_handlers: Dict[
    GrantType,
    Callable[
        [schemas.GrantContext], Awaitable[schemas.TokenResponse]
    ]
] = {
    GrantType.CLIENT_CREDENTIALS: client_credentials_token_handler,
    GrantType.AUTHORIZATION_CODE: authorization_code_token_handler
}
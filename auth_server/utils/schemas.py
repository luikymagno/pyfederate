from pydantic import BaseModel
from dataclasses import dataclass, field, asdict
from typing import Any, List, Dict, Optional, Callable, Awaitable
import bcrypt
import jwt
import time
from fastapi import Request, Response, status
from fastapi.responses import RedirectResponse

from . import constants, exceptions
from .constants import TokenClaim, ErrorCode
from .import tools

######################################## Token ########################################


@dataclass
class TokenInfo():
    subject: str
    issuer: str
    issued_at: int
    expiration: int
    client_id: str
    scopes: List[str]
    id: str = field(default_factory=tools.generate_uuid)
    additional_info: Dict[str, str] = field(default_factory=dict)

    def to_jwt_payload(self) -> Dict[str, Any]:
        payload = {
            **self.additional_info,
            TokenClaim.JWT_ID.value: self.id,
            TokenClaim.SUBJECT.value: self.subject,
            TokenClaim.ISSUER.value: self.issuer,
            TokenClaim.ISSUED_AT.value: self.issued_at,
            TokenClaim.EXPIRATION.value: self.expiration,
            TokenClaim.CLIENT_ID.value: self.client_id,
            TokenClaim.SCOPE.value: " ".join(self.scopes)
        }

        return payload


@dataclass
class BearerToken:
    id: str
    info: TokenInfo
    token: str


@dataclass
class TokenModel():
    id: str
    issuer: str
    expires_in: int

    def generate_token(
        self,
        client_id: str,
        subject: str,
        scopes: List[str],
        additional_claims: Dict[str, str]
    ) -> BearerToken:
        raise NotImplementedError()

    def to_output(self) -> "TokenModelOut":
        raise NotImplementedError()


@dataclass
class TokenModelUpsert(TokenModel):
    token_type: constants.TokenType
    key_id: str | None

    def to_db_dict(self) -> Dict[str, Any]:
        self_dict = asdict(self)

        self_dict["token_type"] = self.token_type.value
        return self_dict

    def __post_init__(self) -> None:
        if (self.token_type == constants.TokenType.JWT and self.key_id is None):
            raise ValueError("JWT tokens must be associated to a key")


@dataclass
class JWTTokenModel(TokenModel):
    key_id: str
    key: str
    signing_algorithm: constants.SigningAlgorithm

    def generate_token(
        self,
        client_id: str,
        subject: str,
        scopes: List[str],
        additional_claims: Dict[str, str]
    ) -> BearerToken:

        timestamp_now = int(time.time())
        token_info = TokenInfo(
            subject=subject,
            issuer=self.issuer,
            issued_at=timestamp_now,
            expiration=timestamp_now + self.expires_in,
            client_id=client_id,
            scopes=scopes,
            additional_info=additional_claims
        )

        return BearerToken(
            id=token_info.id,
            info=token_info,
            token=jwt.encode(
                payload=token_info.to_jwt_payload(),
                key=self.key,
                algorithm=self.signing_algorithm.value
            )
        )

    def to_output(self) -> "TokenModelOut":

        return TokenModelOut(
            id=self.id,
            issuer=self.issuer,
            expires_in=self.expires_in,
            token_type=constants.TokenType.JWT,
            key_id=self.key_id,
            signing_algorithm=self.signing_algorithm
        )

#################### API Models ####################


@dataclass
class TokenModelIn(TokenModel):
    token_type: constants.TokenType
    key_id: constants.JWK_IDS_LITERAL | None

    def __post_init__(self) -> None:

        if (self.token_type == constants.TokenType.JWT and self.key_id is None):
            raise ValueError("JWT Token models must have a key_id")

    def to_upsert(self) -> TokenModelUpsert:
        return TokenModelUpsert(
            id=self.id,
            issuer=self.issuer,
            expires_in=self.expires_in,
            token_type=self.token_type,
            key_id=self.key_id,
        )


@dataclass
class TokenModelOut(TokenModel):
    token_type: constants.TokenType
    key_id: str | None
    signing_algorithm: constants.SigningAlgorithm | None

######################################## Scope ########################################


@dataclass
class Scope():
    name: str
    description: str

    def to_output(self) -> "ScopeOut":
        return ScopeOut(
            name=self.name,
            description=self.description
        )


@dataclass
class ScopeUpsert(Scope):
    def to_db_dict(self) -> Dict[str, Any]:
        self_dict = asdict(self)
        return self_dict

#################### API Models ####################


@dataclass
class ScopeIn(Scope):

    def to_upsert(self) -> ScopeUpsert:
        return ScopeUpsert(
            name=self.name,
            description=self.description
        )


@dataclass
class ScopeOut(Scope):
    pass

######################################## Client ########################################


@dataclass(kw_only=True)
class ClientBase():
    authn_method: constants.ClientAuthnMethod
    redirect_uris: List[str]
    response_types: List[constants.ResponseType]
    grant_types: List[constants.GrantType]
    scopes: List[str]
    is_pcke_required: bool
    extra_params: Dict[str, str] = field(default_factory=dict)


@dataclass
class ClientUpsert(ClientBase):
    token_model_id: str
    id: str = field(default_factory=tools.generate_client_id, init=False)
    secret: str | None = field(init=False)

    def __post_init__(self) -> None:
        if (self.authn_method == constants.ClientAuthnMethod.NONE and self.is_pcke_required is False):
            raise ValueError(
                "Client without authentication method must require PCKE")
        if (self.authn_method == constants.ClientAuthnMethod.SECRET):
            self.secret = tools.generate_client_secret()

    def to_db_dict(self) -> Dict[str, Any]:
        self_dict = asdict(self)
        self_dict["redirect_uris"] = ",".join(self.redirect_uris)
        self_dict["response_types"] = ",".join(
            [r.value for r in self.response_types])
        self_dict["grant_types"] = ",".join(
            [gt.value for gt in self.grant_types])
        self_dict["authn_method"] = self.authn_method.value
        if (self.authn_method == constants.ClientAuthnMethod.SECRET):
            self_dict["hashed_secret"] = tools.hash_secret(
                secret=self.secret)  # type: ignore
        self_dict["extra_params"] = tools.to_base64_string(
            extra_params=self.extra_params)
        self_dict.pop("secret")
        return self_dict


@dataclass
class Client(ClientBase):
    id: str
    token_model: TokenModel
    hashed_secret: str | None
    secret: str | None = None

    def to_output(self) -> "ClientOut":
        return ClientOut(
            id=self.id,
            authn_method=self.authn_method,
            secret=self.secret,
            redirect_uris=self.redirect_uris,
            response_types=self.response_types,
            grant_types=self.grant_types,
            scopes=self.scopes,
            is_pcke_required=self.is_pcke_required,
            token_model_id=self.token_model.id,
            extra_params=self.extra_params
        )

    def is_authenticated(self, client_secret: str) -> bool:
        if (self.hashed_secret is None):
            return False

        return bcrypt.checkpw(
            password=client_secret.encode(constants.SECRET_ENCODING),
            hashed_password=self.hashed_secret.encode(
                constants.SECRET_ENCODING)
        )

    def are_scopes_allowed(self, requested_scopes: List[str]) -> bool:
        return set(requested_scopes).issubset(set(self.scopes))

    def owns_redirect_uri(self, redirect_uri: str) -> bool:
        return redirect_uri in self.redirect_uris

    def is_response_type_allowed(self, response_type: constants.ResponseType) -> bool:
        return response_type in self.response_types

    def is_grant_type_allowed(self, grant_type: constants.GrantType) -> bool:
        return grant_type in self.grant_types

#################### API Models ####################


@dataclass
class ClientIn(ClientBase):
    token_model_id: str

    def to_upsert(self) -> ClientUpsert:
        return ClientUpsert(
            authn_method=self.authn_method,
            redirect_uris=self.redirect_uris,
            response_types=self.response_types,
            scopes=self.scopes,
            grant_types=self.grant_types,
            is_pcke_required=self.is_pcke_required,
            token_model_id=self.token_model_id,
            extra_params=self.extra_params
        )


@dataclass
class ClientOut(ClientBase):
    id: str
    token_model_id: str
    secret: str | None = None

######################################## OAuth ########################################


@dataclass
class GrantContext:
    client: Client
    client_secret: str | None
    token_model: TokenModel
    requested_scopes: List[str]
    redirect_uri: str | None
    authz_code: str | None
    code_verifier: str | None


@dataclass
class TokenResponse():
    access_token: str
    expires_in: int
    token_type: str = field(default=constants.BEARER_TOKEN_TYPE)
    refresh_token: str | None = None
    scope: str | None = None

######################################## Session ########################################


@dataclass
class AuthnSession():
    id: str
    tracking_id: str
    correlation_id: str
    callback_id: str | None
    client_id: str
    redirect_uri: str
    requested_scopes: List[str]
    state: str
    auth_policy_id: str
    next_authn_step_id: str
    user_id: str | None
    authz_code: str | None
    authz_code_creation_timestamp: int | None
    code_challenge: str | None
    params: Dict[str, Any] = field(default_factory=dict)

######################################## Auth Policy ########################################


AUTHN_POLICIES: Dict[str, "AuthnPolicy"] = {}
AUTHN_STEPS: Dict[str, "AuthnStep"] = {}


@dataclass
class AuthnStepResult():
    status: constants.AuthnStatus

    def get_response(self, session: AuthnSession) -> Response:
        raise NotImplementedError()


@dataclass
class AuthnStepInProgressResult(AuthnStepResult):
    response: Response
    status: constants.AuthnStatus = field(
        default=constants.AuthnStatus.IN_PROGRESS, init=False)

    def get_response(self, session: AuthnSession) -> Response:
        return self.response


@dataclass
class AuthnStepFailureResult(AuthnStepResult):
    error_description: str
    status: constants.AuthnStatus = field(
        default=constants.AuthnStatus.FAILURE, init=False
    )

    def get_response(self, session: AuthnSession) -> Response:
        return RedirectResponse(
            url=tools.prepare_redirect_url(url=session.redirect_uri, params={
                "error": ErrorCode.ACCESS_DENIED.value,
                "error_description": self.error_description,
            }),
            status_code=status.HTTP_303_SEE_OTHER
        )


@dataclass
class AuthnStepSuccessResult(AuthnStepResult):
    status: constants.AuthnStatus = field(
        default=constants.AuthnStatus.SUCCESS, init=False
    )

    def get_response(self, session: AuthnSession) -> Response:

        if (session.authz_code is None):
            raise RuntimeError("The authorization code cannot be None")

        return RedirectResponse(
            url=tools.prepare_redirect_url(url=session.redirect_uri, params={
                "code": session.authz_code,
                "state": session.state,
            }),
            status_code=status.HTTP_303_SEE_OTHER
        )


@dataclass
class AuthnStep():
    id: str
    authn_func: Callable[
        [
            AuthnSession,
            Request
        ],
        AuthnStepResult | Awaitable[AuthnStepResult]
    ]
    success_next_step: Optional["AuthnStep"]
    failure_next_step: Optional["AuthnStep"]

    def __post_init__(self) -> None:
        # Make sure the step id is unique
        if (self.id in AUTHN_STEPS):
            raise exceptions.AuthnStepAlreadyExistsException()
        AUTHN_STEPS[self.id] = self


async def default_failure_authn_func(session: AuthnSession, request: Request) -> AuthnStepResult:
    return AuthnStepFailureResult(error_description="access denied")

# Step that always returns failure
default_failure_step = AuthnStep(
    id="default_failure_step_42",
    authn_func=default_failure_authn_func,
    success_next_step=None,
    failure_next_step=None
)


@dataclass
class AuthnPolicy():
    id: str
    is_available: Callable[[Client, Request], bool]
    first_step: AuthnStep
    get_extra_token_claims: Callable[[
        AuthnSession], Dict[str, str]] | None = None

    def __post_init__(self) -> None:
        # Make sure the policy id is unique
        if (self.id in AUTHN_POLICIES):
            raise exceptions.AuthnPolicyAlreadyExistsException()
        AUTHN_POLICIES[self.id] = self

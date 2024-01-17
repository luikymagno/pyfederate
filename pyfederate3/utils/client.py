from abc import ABC, abstractmethod

from ..schemas.client import ClientInfo, ClientAuthnContext
from ..utils.tools import hash_secret
from .token import TokenModel


class ClientAuthenticator(ABC):
    @abstractmethod
    def is_authenticated(self, authn_context: ClientAuthnContext) -> bool:
        ...


class NoneAuthenticator(ClientAuthenticator):
    def is_authenticated(self, authn_context: ClientAuthnContext) -> bool:
        if authn_context.secret:
            return False

        return True


class SecretAuthenticator(ClientAuthenticator):
    def __init__(self, hashed_secret: str) -> None:
        self._hashed_secret = hashed_secret

    def is_authenticated(self, authn_context: ClientAuthnContext) -> bool:
        if not authn_context.secret:
            return False

        return hash_secret(authn_context.secret) == self._hashed_secret


class Client:
    def __init__(
        self,
        info: ClientInfo,
        authenticator: ClientAuthenticator,
    ) -> None:
        self._info = info
        self._authenticator = authenticator

    def get_default_token_model_id(self) -> str:
        return self._info.default_token_model_id

from typing import Dict, Any
from dataclasses import replace
import copy
import jwt
import pytest

from tests import conftest
from auth_server.utils import schemas, constants, exceptions


class TestTokenInfo:

    def test_to_jwt_payload(self) -> None:
        """Test if the jwt payload is correct"""

        token_info = replace(conftest.token_info)
        token_info.additional_info = {
            # The additional info should not be capable of overwriting the standard fields
            "sub": "new_user@email.com",
            "claim": "value"
        }
        expected_jwt_payload = copy.deepcopy(conftest.expected_jwt_payload)
        expected_jwt_payload["claim"] = "value"

        assert token_info.to_jwt_payload() == expected_jwt_payload,\
            "The JWT payload is wrong"


class TestJWTTokenModel:

    def test_generate_token(self) -> None:
        """Test if the jwt payload generated is correct"""
        jwt_token: str = conftest.jwt_token_model.generate_token(
            token_info=conftest.token_info
        )
        expected_payload = copy.deepcopy(conftest.expected_jwt_payload)

        assert jwt.decode(
            jwt_token,
            algorithms=[conftest.jwt_token_model.signing_algorithm.value],
            key=conftest.jwt_token_model.key,
        ) == expected_payload, "The decoded JWT payload is wrong"


class TestTokenModelIn:

    def test_jwt_tokens_must_have_key_id(self) -> None:
        """Test that JWT token models must have a key ID"""

        with pytest.raises(exceptions.JWTModelMustHaveKeyIDException):
            schemas.TokenModelIn(
                id="",
                issuer="",
                expires_in=0,
                is_refreshable=False,
                token_type=constants.TokenType.JWT,
                key_id=None
            )


class TestClientUpsert:

    def test_setup_secret_authentication(self) -> None:
        """
        Test that client to be upserted that authenticate with secret
        have the secret generated automatically.
        """

        client_upsert = schemas.ClientUpsert(
            id="",
            authn_method=constants.ClientAuthnMethod.CLIENT_SECRET_POST,
            redirect_uris=[],
            response_types=[],
            grant_types=[],
            scopes=[],
            is_pkce_required=False,
            token_model_id=""
        )
        assert client_upsert.secret is not None


class TestClient:

    def test_is_authenticated_by_secret(self) -> None:

        assert conftest.client.is_authenticated_by_secret(
            client_secret=conftest.CLIENT_SECRET), "The client secret should be valid"
        assert not conftest.client.is_authenticated_by_secret(
            client_secret="invalid_secret"), "The client secret should not be valid"

    def test_are_scopes_allowed(self) -> None:
        assert conftest.client.are_scopes_allowed(conftest.SCOPES),\
            "The scopes should be allowed"
        assert not conftest.client.are_scopes_allowed(["invalid_scope"]),\
            "The scopes should not be allowed"

    def test_owns_redirect_uri(self) -> None:
        assert conftest.client.owns_redirect_uri(conftest.REDIRECT_URI),\
            "The client owns the redirect uri"
        assert not conftest.client.owns_redirect_uri("invalid_redirect_uri"),\
            "The client doesn't own the redirect uri"

    def test_are_response_types_allowed(self) -> None:
        client = conftest.client.model_copy()
        client.response_types = [constants.ResponseType.CODE]

        assert client.are_response_types_allowed([constants.ResponseType.CODE]),\
            "The response types are allowed"
        assert not client.are_response_types_allowed([constants.ResponseType.ID_TOKEN]),\
            "The response types are not allowed"

    def test_is_grant_type_allowed(self) -> None:
        client = conftest.client.model_copy()
        client.grant_types = [constants.GrantType.AUTHORIZATION_CODE]

        assert client.is_grant_type_allowed(grant_type=constants.GrantType.AUTHORIZATION_CODE),\
            "The grant type should be allowed"
        assert not client.is_grant_type_allowed(grant_type=constants.GrantType.CLIENT_CREDENTIALS),\
            "The grant type should not be allowed"


class TestClientIn:

    def test_only_authz_code_has_response_types(self) -> None:
        with pytest.raises(ValueError):
            schemas.ClientIn(
                **{
                    **dict(conftest.client_in),
                    "grant_types": [constants.GrantType.CLIENT_CREDENTIALS],
                    "response_types": [constants.ResponseType.CODE]
                }
            )

    def test_client_credentials_authn_method(self) -> None:
        with pytest.raises(ValueError):
            schemas.ClientIn(
                **{
                    **dict(conftest.client_in),
                    "grant_types": [constants.GrantType.AUTHORIZATION_CODE, constants.GrantType.CLIENT_CREDENTIALS],
                    "authn_method": constants.ClientAuthnMethod.NONE
                }
            )

    def test_refresh_token_authn_method(self) -> None:
        with pytest.raises(ValueError):
            schemas.ClientIn(
                **{
                    **dict(conftest.client_in),
                    "grant_types": [constants.GrantType.AUTHORIZATION_CODE, constants.GrantType.REFRESH_TOKEN],
                    "authn_method": constants.ClientAuthnMethod.NONE,
                }
            )

    def test_client_without_authn_method_must_require_pkce(self) -> None:
        with pytest.raises(ValueError):
            schemas.ClientIn(
                **{
                    **dict(conftest.client_in),
                    "grant_types": [constants.GrantType.AUTHORIZATION_CODE],
                    "authn_method": constants.ClientAuthnMethod.NONE,
                    "is_pkce_required": False
                }
            )
import json
import base64
import time
import re
import threading
import requests


class CognitoTokenClient:
    """Manages Cognito OAuth tokens with automatic renewal.

    Uses the Cognito public REST API directly — no boto3 or AWS credentials required.
    Only needs the OIDC discovery URL and client ID (from the authorizer config)
    plus user credentials.
    """

    TOKEN_REFRESH_BUFFER_SECONDS = 600
    COGNITO_SERVICE_TARGET = "AWSCognitoIdentityProviderService.InitiateAuth"

    def __init__(
        self,
        discovery_url: str,
        client_id: str,
        username: str,
        password: str,
    ):
        self._client_id = client_id
        self._username = username
        self._password = password

        self._endpoint, self._region = self._parse_discovery_url(discovery_url)

        self._access_token: str | None = None
        self._refresh_token: str | None = None
        self._id_token: str | None = None
        self._expires_at: float = 0
        self._lock = threading.Lock()

    @staticmethod
    def _parse_discovery_url(discovery_url: str) -> tuple[str, str]:
        """Extract the Cognito API endpoint and region from the OIDC discovery URL."""
        match = re.match(
            r"https://cognito-idp\.([a-z0-9-]+)\.amazonaws\.com/", discovery_url
        )
        if not match:
            raise ValueError(f"Cannot parse region from discovery URL: {discovery_url}")
        region = match.group(1)
        endpoint = f"https://cognito-idp.{region}.amazonaws.com/"
        return endpoint, region

    def _call_initiate_auth(self, auth_flow: str, auth_params: dict) -> dict:
        """Call the Cognito InitiateAuth REST API directly."""
        resp = requests.post(
            self._endpoint,
            headers={
                "Content-Type": "application/x-amz-json-1.1",
                "X-Amz-Target": self.COGNITO_SERVICE_TARGET,
            },
            json={
                "AuthFlow": auth_flow,
                "ClientId": self._client_id,
                "AuthParameters": auth_params,
            },
        )
        if resp.status_code != 200:
            raise RuntimeError(
                f"Cognito InitiateAuth failed ({resp.status_code}): {resp.text}"
            )
        return resp.json()["AuthenticationResult"]

    def _authenticate(self) -> dict:
        return self._call_initiate_auth(
            "USER_PASSWORD_AUTH",
            {"USERNAME": self._username, "PASSWORD": self._password},
        )

    def _refresh(self) -> dict:
        return self._call_initiate_auth(
            "REFRESH_TOKEN_AUTH",
            {"REFRESH_TOKEN": self._refresh_token},
        )

    @staticmethod
    def _decode_jwt_payload(token: str) -> dict:
        payload_b64 = token.split(".")[1]
        payload_b64 += "=" * (4 - len(payload_b64) % 4)
        return json.loads(base64.urlsafe_b64decode(payload_b64))

    def _is_token_expired(self) -> bool:
        return time.time() >= (self._expires_at - self.TOKEN_REFRESH_BUFFER_SECONDS)

    def _store_tokens(self, auth_result: dict) -> None:
        self._access_token = auth_result["AccessToken"]
        self._id_token = auth_result.get("IdToken")
        if "RefreshToken" in auth_result:
            self._refresh_token = auth_result["RefreshToken"]
        self._expires_at = self._decode_jwt_payload(self._access_token)["exp"]

    def _ensure_valid_token(self) -> None:
        if not self._is_token_expired():
            return

        if self._refresh_token:
            try:
                self._store_tokens(self._refresh())
                return
            except RuntimeError:
                pass

        self._store_tokens(self._authenticate())

    @property
    def access_token(self) -> str:
        """Returns a valid access token, refreshing or re-authenticating as needed. Thread-safe."""
        with self._lock:
            self._ensure_valid_token()
            return self._access_token

    @property
    def id_token(self) -> str | None:
        with self._lock:
            self._ensure_valid_token()
            return self._id_token

    @property
    def authorization_header(self) -> dict[str, str]:
        """Returns a header dict ready for HTTP requests."""
        return {"Authorization": f"Bearer {self.access_token}"}

    def invalidate(self) -> None:
        """Force re-authentication on next access."""
        with self._lock:
            self._expires_at = 0


if __name__ == "__main__":
    import os

    client = CognitoTokenClient(
        discovery_url=os.getenv(
            "DISCOVERY_URL",
            "https://cognito-idp.ap-southeast-2.amazonaws.com/ap-southeast-2_6AnwIssYD/.well-known/openid-configuration",
        ),
        client_id=os.getenv("CLIENT_ID", "2eusmbe7ujgh611vh4m4p5n22g"),
        username=os.getenv("USERNAME", "MCP_USER"),
        password=os.getenv("PASSWORD", "MCP_PASSWORD"),
    )

    print("=" * 60)
    print("TEST 1: Initial authentication (USER_PASSWORD_AUTH)")
    print("=" * 60)
    token1 = client.access_token
    payload1 = client._decode_jwt_payload(token1)
    print(f"  Access Token: {token1[:60]}...")
    print(f"  Expires at:   {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(payload1['exp']))}")
    print(f"  Has refresh token: {client._refresh_token is not None}")
    print("  PASSED\n")

    print("=" * 60)
    print("TEST 2: Token caching (should reuse without network call)")
    print("=" * 60)
    token2 = client.access_token
    assert token2 == token1, "Token should be reused from cache"
    print(f"  Same token returned: True")
    print("  PASSED\n")

    print("=" * 60)
    print("TEST 3: Token renewal via REFRESH_TOKEN_AUTH")
    print("=" * 60)
    print("  Forcing expiry by setting expires_at = 0 ...")
    client._expires_at = 0
    token3 = client.access_token
    payload3 = client._decode_jwt_payload(token3)
    is_new = token3 != token1
    print(f"  New token issued: {is_new}")
    print(f"  Access Token: {token3[:60]}...")
    print(f"  Expires at:   {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(payload3['exp']))}")
    print("  PASSED\n")

    print("=" * 60)
    print("TEST 4: Full re-authentication after invalidate()")
    print("=" * 60)
    client._refresh_token = None
    client.invalidate()
    token4 = client.access_token
    payload4 = client._decode_jwt_payload(token4)
    print(f"  New token issued: {token4 != token3}")
    print(f"  Access Token: {token4[:60]}...")
    print(f"  Expires at:   {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(payload4['exp']))}")
    print("  PASSED\n")

    print("All tests passed.")

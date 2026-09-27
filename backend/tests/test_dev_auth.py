from fastapi.security import HTTPAuthorizationCredentials
from fastapi import HTTPException

import healsync_backend.auth as auth
from healsync_backend.auth import current_claims, issue_dev_token
from healsync_backend.contracts import UserRecord
import healsync_backend.routes as routes


def test_dev_token_roundtrip() -> None:
    token = issue_dev_token("dev:alice@example.com", "alice@example.com")
    claims = current_claims(HTTPAuthorizationCredentials(scheme="Bearer", credentials=token))

    assert claims["uid"] == "dev:alice@example.com"
    assert claims["email"] == "alice@example.com"


def test_demo_auth_requires_a_configured_jwt_secret(monkeypatch) -> None:
    monkeypatch.setattr(auth, "ENVIRONMENT", "demo")
    monkeypatch.delenv("DEV_JWT_SECRET", raising=False)

    try:
        auth.issue_dev_token("dev:alice@example.com", "alice@example.com")
    except RuntimeError as error:
        assert str(error) == "DEV_JWT_SECRET must be configured when demo authentication is enabled"
    else:
        raise AssertionError("Hosted demo auth must not use the local development secret")


def test_dev_login_rejects_existing_account_role_mismatch(monkeypatch) -> None:
    existing_user = UserRecord(
        id="supplier-id",
        firebase_uid="dev:supplier@healsync.com",
        email="supplier@healsync.com",
        name="Apollo MedSupply",
        role="patient",
    )

    class ExistingUserRepository:
        def get_by_firebase_uid(self, firebase_uid: str) -> UserRecord:
            assert firebase_uid == existing_user.firebase_uid
            return existing_user

        def create_or_update(self, user: UserRecord) -> UserRecord:
            raise AssertionError("A role mismatch must not update the existing account")

    monkeypatch.setattr(routes, "user_repository", lambda: ExistingUserRepository())

    try:
        routes.dev_login({"email": existing_user.email, "password": "demo", "role": "supplier"})
    except HTTPException as error:
        assert error.status_code == 403
        assert error.detail == "This account is registered as patient. Choose the patient login."
    else:
        raise AssertionError("Expected a role mismatch to be rejected")


def test_dev_login_rejects_unregistered_email() -> None:
    try:
        routes.dev_login({"email": "other@example.com", "password": "demo", "role": "patient"})
    except HTTPException as error:
        assert error.status_code == 401
    else:
        raise AssertionError("Only the named demo accounts may sign in")


def test_dev_login_creates_canonical_named_account(monkeypatch) -> None:
    created: list[UserRecord] = []

    class EmptyRepository:
        def get_by_firebase_uid(self, firebase_uid: str) -> None:
            assert firebase_uid == "dev:doctor@healsync.com"
            return None

        def create_or_update(self, user: UserRecord) -> UserRecord:
            created.append(user)
            return UserRecord("doctor-id", user.firebase_uid, user.email, user.name, user.role)

    monkeypatch.setattr(routes, "ENABLE_DEV_AUTH", True)
    monkeypatch.setattr(routes, "user_repository", lambda: EmptyRepository())
    monkeypatch.setattr(routes, "issue_dev_token", lambda uid, email: "local-token")
    result = routes.dev_login({"email": "doctor@healsync.com", "password": "demo", "role": "doctor"})

    assert result["role"] == "doctor"
    assert result["id_token"] == "local-token"
    assert created[0].name == "Dr. Meera Rao"


def test_dev_login_rejects_wrong_demo_password() -> None:
    try:
        routes.dev_login({"email": "doctor@healsync.com", "password": "wrong", "role": "doctor"})
    except HTTPException as error:
        assert error.status_code == 401
    else:
        raise AssertionError("The local demo password must be checked")

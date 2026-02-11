import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_signup_success(client: AsyncClient):
    response = await client.post("/auth/signup", json={
        "name": "Alice Smith",
        "email": "alice@example.com",
        "password": "securepassword123",
        "account_slug": "alice-co",
    })
    assert response.status_code == 201
    data = response.json()
    assert data["message"] == "Account created successfully"
    assert data["user"]["email"] == "alice@example.com"
    assert data["user"]["name"] == "Alice Smith"
    assert data["user"]["account_slug"] == "alice-co"
    assert data["user"]["plan"] == "free"

    # Cookie should be set
    assert "access_token" in response.cookies


@pytest.mark.asyncio
async def test_signup_duplicate_email(client: AsyncClient):
    await client.post("/auth/signup", json={
        "name": "User One",
        "email": "dupe@example.com",
        "password": "password123",
        "account_slug": "user-one",
    })
    response = await client.post("/auth/signup", json={
        "name": "User Two",
        "email": "dupe@example.com",
        "password": "password456",
        "account_slug": "user-two",
    })
    assert response.status_code == 409
    assert "email already exists" in response.json()["detail"]


@pytest.mark.asyncio
async def test_signup_duplicate_slug(client: AsyncClient):
    await client.post("/auth/signup", json={
        "name": "User One",
        "email": "one@example.com",
        "password": "password123",
        "account_slug": "same-slug",
    })
    response = await client.post("/auth/signup", json={
        "name": "User Two",
        "email": "two@example.com",
        "password": "password456",
        "account_slug": "same-slug",
    })
    assert response.status_code == 409
    assert "already taken" in response.json()["detail"]


@pytest.mark.asyncio
async def test_signup_short_password(client: AsyncClient):
    response = await client.post("/auth/signup", json={
        "name": "Test",
        "email": "short@example.com",
        "password": "1234",
        "account_slug": "short-pw",
    })
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_signup_invalid_email(client: AsyncClient):
    response = await client.post("/auth/signup", json={
        "name": "Test",
        "email": "not-an-email",
        "password": "password123",
        "account_slug": "bad-email",
    })
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_signup_invalid_slug(client: AsyncClient):
    response = await client.post("/auth/signup", json={
        "name": "Test",
        "email": "test@example.com",
        "password": "password123",
        "account_slug": "AB",
    })
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    # First signup
    await client.post("/auth/signup", json={
        "name": "Login User",
        "email": "login@example.com",
        "password": "mypassword123",
        "account_slug": "login-test",
    })

    # Then login
    response = await client.post("/auth/login", data={
        "username": "login@example.com",
        "password": "mypassword123",
    })
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Logged in successfully"
    assert data["user"]["email"] == "login@example.com"
    assert "access_token" in response.cookies


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    await client.post("/auth/signup", json={
        "name": "Login User",
        "email": "wrongpw@example.com",
        "password": "correctpassword",
        "account_slug": "wrongpw-test",
    })
    response = await client.post("/auth/login", data={
        "username": "wrongpw@example.com",
        "password": "wrongpassword",
    })
    assert response.status_code == 401
    assert "Invalid" in response.json()["detail"]


@pytest.mark.asyncio
async def test_login_nonexistent_user(client: AsyncClient):
    response = await client.post("/auth/login", data={
        "username": "nobody@example.com",
        "password": "somepassword",
    })
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_logout(authenticated_client: AsyncClient):
    response = await authenticated_client.post("/auth/logout")
    assert response.status_code == 200
    assert response.json()["message"] == "Logged out successfully"


@pytest.mark.asyncio
async def test_get_me(authenticated_client: AsyncClient):
    response = await authenticated_client.get("/auth/me")
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "test@example.com"
    assert data["name"] == "Test User"


@pytest.mark.asyncio
async def test_get_me_unauthenticated(client: AsyncClient):
    response = await client.get("/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_dashboard_redirect_unauthenticated(client: AsyncClient):
    response = await client.get("/dashboard", follow_redirects=False)
    assert response.status_code == 303
    assert "/login" in response.headers.get("location", "")


@pytest.mark.asyncio
async def test_logged_in_user_redirected_from_login(authenticated_client: AsyncClient):
    """Logged-in users visiting /login should be redirected to /dashboard."""
    response = await authenticated_client.get("/login", follow_redirects=False)
    assert response.status_code == 303
    assert "/dashboard" in response.headers.get("location", "")


@pytest.mark.asyncio
async def test_logged_in_user_redirected_from_signup(authenticated_client: AsyncClient):
    """Logged-in users visiting /signup should be redirected to /dashboard."""
    response = await authenticated_client.get("/signup", follow_redirects=False)
    assert response.status_code == 303
    assert "/dashboard" in response.headers.get("location", "")


@pytest.mark.asyncio
async def test_logged_in_user_redirected_from_landing(authenticated_client: AsyncClient):
    """Logged-in users visiting / should be redirected to /dashboard."""
    response = await authenticated_client.get("/", follow_redirects=False)
    assert response.status_code == 303
    assert "/dashboard" in response.headers.get("location", "")


@pytest.mark.asyncio
async def test_signup_creates_status_page(client: AsyncClient):
    """Signup should create a default status page for the user."""
    response = await client.post("/auth/signup", json={
        "name": "New User",
        "email": "newuser@example.com",
        "password": "password123",
        "account_slug": "new-user",
    })
    assert response.status_code == 201

    # Status page should exist
    client.cookies.update(response.cookies)
    status_response = await client.get("/s/new-user")
    assert status_response.status_code == 200

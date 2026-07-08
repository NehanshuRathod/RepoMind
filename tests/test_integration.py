import io
import time
import zipfile


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


def register_and_login(client, email, password="Password123!"):
    client.post(
        "/auth/register",
        json={"email": email, "password": password, "full_name": "Tester"},
    )
    response = client.post("/auth/login", data={"username": email, "password": password})
    return response.json()["access_token"]


def test_register_and_login_flow(client):
    response = client.post(
        "/auth/register",
        json={"email": "alice@example.com", "password": "Password123!", "full_name": "Alice"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "alice@example.com"
    assert "id" in body

    login = client.post("/auth/login", data={"username": "alice@example.com", "password": "Password123!"})
    assert login.status_code == 200
    assert login.json()["token_type"] == "bearer"
    assert login.json()["access_token"]


def test_login_with_wrong_password_fails(client):
    client.post(
        "/auth/register",
        json={"email": "bob@example.com", "password": "Password123!", "full_name": "Bob"},
    )
    login = client.post("/auth/login", data={"username": "bob@example.com", "password": "wrongpass"})
    assert login.status_code == 401


def test_project_ownership_is_enforced(client):
    token_a = register_and_login(client, "owner@example.com")
    token_b = register_and_login(client, "other@example.com")

    created = client.post(
        "/projects",
        json={"project_name": "owned"},
        headers=auth_header(token_a),
    )
    assert created.status_code == 201
    project_id = created.json()["id"]

    # Owner can access their own project.
    own = client.get(f"/projects/{project_id}", headers=auth_header(token_a))
    assert own.status_code == 200

    # Another user gets 404 (project not found / not owned).
    other = client.get(f"/projects/{project_id}", headers=auth_header(token_b))
    assert other.status_code == 404

    # Unauthenticated access is rejected.
    anon = client.get(f"/projects/{project_id}")
    assert anon.status_code == 401


def test_zip_upload_indexes_multilanguage_code(client):
    token = register_and_login(client, "carol@example.com")

    py_source = (
        "class Service:\n"
        "    def authenticate(self, email: str) -> bool:\n"
        "        return '@' in email\n"
        "\n"
        "def build_embeddings(texts):\n"
        "    return [t for t in texts]\n"
    )
    js_source = (
        "class Auth {\n"
        "  login(user) {\n"
        "    return validate(user);\n"
        "  }\n"
        "}\n"
        "\n"
        "function hashPassword(password) {\n"
        "  return password + '_hashed';\n"
        "}\n"
    )

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("src/service.py", py_source)
        archive.writestr("src/auth.js", js_source)
    buffer.seek(0)

    upload = client.post(
        "/projects/upload",
        params={"project_name": "uploaded"},
        files={"file": ("repo.zip", buffer.read(), "application/zip")},
        headers=auth_header(token),
    )
    assert upload.status_code == 201
    project_id = upload.json()["id"]

    status = None
    for _ in range(30):
        status = client.get(f"/projects/{project_id}/status", headers=auth_header(token)).json()
        if status["status"] in {"indexed", "failed"}:
            break
        time.sleep(0.2)

    assert status is not None
    assert status["status"] == "indexed", status.get("error")
    assert status["indexed_file_count"] == 2
    assert status["indexed_chunk_count"] > 0
    assert status["progress"] == 100

    # Search returns a well-formed response for the indexed project.
    search = client.post(
        f"/projects/{project_id}/search",
        json={"query": "authentication logic", "top_k": 5},
        headers=auth_header(token),
    )
    assert search.status_code == 200
    assert "results" in search.json()


def test_search_before_indexing_is_rejected(client):
    token = register_and_login(client, "dave@example.com")
    created = client.post(
        "/projects",
        json={"project_name": "empty"},
        headers=auth_header(token),
    )
    project_id = created.json()["id"]
    search = client.post(
        f"/projects/{project_id}/search",
        json={"query": "anything", "top_k": 5},
        headers=auth_header(token),
    )
    assert search.status_code == 400

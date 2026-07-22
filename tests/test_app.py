import http.cookiejar
import json
import sqlite3
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

import start


class ApiClient:
    def __init__(self, base_url):
        self.base_url = base_url
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))

    def request(self, path, method="GET", data=None, expected=200):
        body = None if data is None else json.dumps(data).encode("utf-8")
        headers = {"Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(self.base_url + path, data=body, headers=headers, method=method)
        try:
            response = self.opener.open(request, timeout=4)
            status = response.status
            payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            status = error.code
            payload = json.loads(error.read().decode("utf-8"))
        self.test_status(status, expected, payload)
        return payload

    @staticmethod
    def test_status(actual, expected, payload):
        if actual != expected:
            raise AssertionError("Status %s, esperado %s: %r" % (actual, expected, payload))


class BancaApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        database = Path(cls.temp.name) / "test.sqlite3"
        cls.server = start.create_server("127.0.0.1", 0, database)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = "http://127.0.0.1:%d" % cls.server.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=3)
        cls.temp.cleanup()

    def test_01_health_and_protected_route(self):
        client = ApiClient(self.base_url)
        self.assertTrue(client.request("/api/health")["ok"])
        error = client.request("/api/bootstrap", expected=401)
        self.assertIn("login", error["error"].lower())

        for private_path in ("/data/test.sqlite3", "/start.py", "/.git/config", "/tests/test_app.py"):
            request = urllib.request.Request(self.base_url + private_path)
            with self.assertRaises(urllib.error.HTTPError) as blocked:
                urllib.request.urlopen(request, timeout=4)
            self.assertEqual(blocked.exception.code, 404)

    def test_02_demo_account_is_seeded(self):
        client = ApiClient(self.base_url)
        client.request("/api/auth/login", method="POST", data={"email": start.DEMO_EMAIL, "password": start.DEMO_PASSWORD})
        data = client.request("/api/bootstrap")
        self.assertEqual(data["user"]["email"], start.DEMO_EMAIL)
        self.assertEqual(len(data["products"]), len(start.DEMO_PRODUCTS))
        self.assertEqual(data["settings"]["businessName"], "Banca Central")
        with start.connect_db(self.server.db_path) as database:
            iterations = database.execute(
                "SELECT password_iterations FROM users WHERE email = ?", (start.DEMO_EMAIL,)
            ).fetchone()["password_iterations"]
        self.assertEqual(iterations, start.PASSWORD_ITERATIONS)

    def test_03_invalid_login_is_rejected(self):
        client = ApiClient(self.base_url)
        payload = client.request(
            "/api/auth/login",
            method="POST",
            data={"email": start.DEMO_EMAIL, "password": "senha-errada"},
            expected=401,
        )
        self.assertIn("incorretos", payload["error"])

    def test_04_registration_inventory_and_sale_flow(self):
        client = ApiClient(self.base_url)
        created = client.request(
            "/api/auth/register",
            method="POST",
            data={"name": "Joana Silva", "email": "joana@example.com", "password": "Senha1234"},
            expected=201,
        )
        self.assertEqual(created["user"]["name"], "Joana Silva")
        self.assertEqual(client.request("/api/bootstrap")["products"], [])

        result = client.request(
            "/api/products",
            method="POST",
            data={"name": "Café gelado", "category": "Bebidas", "price": 8.5, "stock": 10, "minStock": 2, "barcode": "123"},
            expected=201,
        )
        product = result["product"]
        self.assertEqual(product["price"], 8.5)

        client.request(
            "/api/products/%s" % product["id"],
            method="PATCH",
            data={"stock": 7, "price": 9},
        )
        sale = client.request(
            "/api/sales",
            method="POST",
            data={"paymentMethod": "pix", "items": [{"productId": product["id"], "quantity": 3}]},
            expected=201,
        )["sale"]
        self.assertEqual(sale["total"], 27)
        bootstrap = client.request("/api/bootstrap")
        self.assertEqual(bootstrap["products"][0]["stock"], 4)
        self.assertEqual(bootstrap["sales"][0]["items"][0]["quantity"], 3)

        insufficient = client.request(
            "/api/sales",
            method="POST",
            data={"paymentMethod": "dinheiro", "items": [{"productId": product["id"], "quantity": 5}]},
            expected=409,
        )
        self.assertIn("insuficiente", insufficient["error"])
        self.assertEqual(client.request("/api/bootstrap")["products"][0]["stock"], 4)

    def test_05_accounts_are_isolated(self):
        first = ApiClient(self.base_url)
        first.request(
            "/api/auth/register",
            method="POST",
            data={"name": "Primeira Conta", "email": "first@example.com", "password": "Senha1234"},
            expected=201,
        )
        product = first.request(
            "/api/products",
            method="POST",
            data={"name": "Produto privado", "category": "Teste", "price": 4, "stock": 1, "minStock": 0},
            expected=201,
        )["product"]

        second = ApiClient(self.base_url)
        second.request(
            "/api/auth/register",
            method="POST",
            data={"name": "Segunda Conta", "email": "second@example.com", "password": "Senha1234"},
            expected=201,
        )
        self.assertEqual(second.request("/api/bootstrap")["products"], [])
        second.request(
            "/api/products/%s" % product["id"],
            method="PATCH",
            data={"stock": 999},
            expected=404,
        )

    def test_06_settings_password_and_logout(self):
        client = ApiClient(self.base_url)
        client.request(
            "/api/auth/register",
            method="POST",
            data={"name": "Carlos Lima", "email": "carlos@example.com", "password": "Senha1234"},
            expected=201,
        )
        client.request(
            "/api/settings",
            method="PUT",
            data={"businessName": "Banca do Carlos", "merchantName": "CARLOS LIMA", "city": "CAMPINAS", "pixKey": "carlos@example.com", "whatsapp": "+55 19 99999-9999"},
        )
        self.assertEqual(client.request("/api/bootstrap")["settings"]["whatsapp"], "5519999999999")
        other_session = ApiClient(self.base_url)
        other_session.request(
            "/api/auth/login",
            method="POST",
            data={"email": "carlos@example.com", "password": "Senha1234"},
        )
        client.request(
            "/api/account/password",
            method="PUT",
            data={"currentPassword": "Senha1234", "newPassword": "SenhaNova5678"},
        )
        self.assertEqual(client.request("/api/bootstrap")["user"]["email"], "carlos@example.com")
        other_session.request("/api/bootstrap", expected=401)
        client.request("/api/auth/logout", method="POST", data={})
        client.request("/api/bootstrap", expected=401)
        client.request(
            "/api/auth/login",
            method="POST",
            data={"email": "carlos@example.com", "password": "SenhaNova5678"},
        )

    def test_07_legacy_password_hash_is_migrated_without_lockout(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "legacy.sqlite3"
            salt, digest = start.hash_password(
                "SenhaAntiga123", iterations=start.LEGACY_PASSWORD_ITERATIONS
            )
            database = sqlite3.connect(str(path))
            database.execute(
                """
                CREATE TABLE users (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    email TEXT NOT NULL UNIQUE,
                    password_salt TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            database.execute(
                "INSERT INTO users(id, name, email, password_salt, password_hash, created_at) VALUES(?,?,?,?,?,?)",
                ("legacy-user", "Conta Legada", "legacy@example.com", salt, digest, start.utc_now()),
            )
            database.commit()
            database.close()

            start.init_db(path)
            with start.connect_db(path) as migrated:
                user = migrated.execute(
                    "SELECT * FROM users WHERE email = ?", ("legacy@example.com",)
                ).fetchone()
            self.assertEqual(user["password_iterations"], start.LEGACY_PASSWORD_ITERATIONS)
            self.assertTrue(
                start.verify_password(
                    "SenhaAntiga123",
                    user["password_salt"],
                    user["password_hash"],
                    user["password_iterations"],
                )
            )


if __name__ == "__main__":
    unittest.main()

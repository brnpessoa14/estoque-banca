"""Teste de integração opcional da API serverless com PostgreSQL."""

import http.client
import json
import os
import threading
import unittest
import uuid
from http import cookies
from http.server import ThreadingHTTPServer


class ServerlessApiClient:
    def __init__(self, port):
        self.port = port
        self.cookie = ""

    def request(self, path, method="GET", data=None, expected=200):
        body = None if data is None else json.dumps(data).encode("utf-8")
        headers = {"Accept": "application/json", "Host": "127.0.0.1:%d" % self.port}
        if body is not None:
            headers["Content-Type"] = "application/json"
        if self.cookie:
            headers["Cookie"] = self.cookie
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=15)
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        payload = json.loads(response.read().decode("utf-8"))
        set_cookie = response.getheader("Set-Cookie")
        if set_cookie:
            jar = cookies.SimpleCookie(set_cookie)
            session = jar.get("banca_session")
            self.cookie = "banca_session=%s" % session.value if session and session.value else ""
        connection.close()
        if response.status != expected:
            raise AssertionError("Status %s, esperado %s: %r" % (response.status, expected, payload))
        return payload


@unittest.skipUnless(os.environ.get("DATABASE_URL"), "DATABASE_URL não configurada")
class PostgresIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from api.index import PostgresDatabase, handler

        cls.database_class = PostgresDatabase
        cls.email = "integration-%s@example.invalid" % uuid.uuid4().hex
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.port = cls.server.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=3)
        with cls.database_class() as database:
            database.execute("DELETE FROM users WHERE email = ?", (cls.email,))

    def test_serverless_registration_inventory_and_sale(self):
        client = ServerlessApiClient(self.port)
        self.assertTrue(client.request("/api?route=health")["ok"])
        created = client.request(
            "/api?route=auth/register",
            method="POST",
            data={"name": "Teste Integração", "email": self.email, "password": "Senha1234"},
            expected=201,
        )
        self.assertEqual(created["user"]["email"], self.email)
        product = client.request(
            "/api?route=products",
            method="POST",
            data={
                "name": "Produto PostgreSQL",
                "category": "Teste",
                "price": 12.5,
                "stock": 4,
                "minStock": 1,
                "barcode": "integration-test",
            },
            expected=201,
        )["product"]
        sale = client.request(
            "/api?route=sales",
            method="POST",
            data={
                "paymentMethod": "pix",
                "items": [{"productId": product["id"], "quantity": 2}],
            },
            expected=201,
        )["sale"]
        self.assertEqual(sale["total"], 25)
        bootstrap = client.request("/api?route=bootstrap")
        self.assertEqual(bootstrap["products"][0]["stock"], 2)
        self.assertEqual(bootstrap["sales"][0]["items"][0]["quantity"], 2)


if __name__ == "__main__":
    unittest.main()

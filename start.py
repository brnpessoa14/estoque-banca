#!/usr/bin/env python3
"""
Script para iniciar PDV Banca de Jornal localmente
Funciona com Python 3.7+
"""

import http.server
import socketserver
import os
import webbrowser
from threading import Timer

PORT = 8000
DIRECTORY = os.path.dirname(os.path.abspath(__file__))

class MyHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)
    
    def end_headers(self):
        # Desabilita cache para evitar stale assets
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
        super().end_headers()

def open_browser():
    """Abre o navegador após 1 segundo"""
    webbrowser.open(f'http://localhost:{PORT}')

print("=" * 50)
print("  PDV Banca de Jornal")
print("=" * 50)
print()
print(f"[+] Servidor iniciado em http://localhost:{PORT}")
print(f"[+] Diretório: {DIRECTORY}")
print("[*] Abrindo navegador em 1 segundo...")
print("[*] Pressione Ctrl+C para parar")
print()

# Abre navegador após 1 segundo
timer = Timer(1.0, open_browser)
timer.daemon = True
timer.start()

try:
    with socketserver.TCPServer(("", PORT), MyHTTPRequestHandler) as httpd:
        httpd.serve_forever()
except KeyboardInterrupt:
    print("\n[*] Servidor parado.")

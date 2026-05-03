# ⚡ Início Rápido — PDV Banca

## Opção 1: Modo Offline (Mais Rápido ⚡)

Ideal para teste rápido. Dados salvos apenas no navegador.

### Windows

```powershell
cd c:\estoque-banca
python start.py
# Navegador abre automaticamente em http://localhost:8000
```

Ou:

```powershell
cd c:\estoque-banca
.\start.bat
```

Ou simplesmente abra `index.html` no navegador (duplo clique).

### macOS / Linux

```bash
cd ~/estoque-banca
python3 start.py
# Navegador abre automaticamente
```

---

## Opção 2: Com Supabase (Produção 🔒)

Dados sincronizados, autenticação segura, backup automático.

### Pré-requisitos

1. Conta Supabase (gratuita): https://app.supabase.com
2. Node.js instalado (ou Python 3)

### Setup (5 minutos)

**1. Criar banco no Supabase**
```
app.supabase.com → New Project → Escolha region, defina senha
Aguarde inicialização (2-3 min)
```

**2. Executar SQL**
```
Dashboard → SQL Editor → New Query
Cole conteúdo de supabase-setup.sql
Execute (▶ button)
```

**3. Configurar OAuth (Google)**
```
Dashboard → Authentication → Providers → Google (habilitado/on)
Clique "Google"
Abra Google Console:
  - Vá para console.cloud.google.com
  - Create Project → "estoque-banca"
  - Ative Google+ API
  - Crie OAuth 2.0 credentials (Web application)
  - Callback URL: https://YOUR_PROJECT_ID.supabase.co/auth/v1/callback
  - Copie Client ID e Client Secret
Volte Supabase → Cole credenciais
Salve
```

**4. Atualizar index.html**
```
Abra index.html no editor
Localize linhas ~780:
  const SUPABASE_URL = 'https://YOUR_PROJECT_ID.supabase.co'
  const SUPABASE_ANON_KEY = 'YOUR_ANON_KEY'

Substitua com valores de Dashboard → Settings → API:
  - Project URL
  - anon (não service_role!)

Salve
```

**5. Iniciar servidor**
```bash
cd c:\estoque-banca

# Opção A: Python
python start.py

# Opção B: Node (instala primeiro: npm install)
npm run serve
```

**6. Testar**
```
Abra http://localhost:8000
Clique ENTRAR → Autentica com Google
Clique SINCRONIZAR → OK (envia dados para Supabase)
Verifique: Dashboard → Table Editor → products/sales
```

---

## 🛠️ Troubleshooting

| Problema | Solução |
|----------|---------|
| Porta 8000 já em uso | Use outra porta: `python -m http.server 9000` |
| "Supabase não configurado" | Deixe em branco para modo offline |
| OAuth não funciona | Verifique callback URL no Supabase |
| Dados não sincronizam | Faça login (botão deve dizer SAIR) antes de sincronizar |

---

## 📚 Próximos Passos

- Leia `README.md` para funcionalidades completas
- Leia `SUPABASE_README.md` para guia detalhado
- F12 (DevTools) → Console para logs de erro

---

**✅ Pronto para usar!**

Modo offline funciona agora mesmo. Modo Supabase só precisa de credenciais preenchidas (5 min de setup).

Guia de Configuração — Integração Supabase + OAuth + RLS

## 1) Criar projeto no Supabase
- Acesse https://app.supabase.com → New project
- Defina nome, senha e região
- Aguarde a inicialização

## 2) Configurar OAuth
- Dashboard → Authentication → Providers → Google (ou Github)
- Configure credenciais OAuth (Google Console / Github)
- Adicione redirect URL: `https://YOUR_PROJECT_ID.supabase.co/auth/v1/callback`

## 3) Criar tabelas e RLS
- Dashboard → SQL Editor → New Query
- Cole todo o conteúdo de `supabase-setup.sql` e execute
- Verifique se as tabelas `products`, `sales`, `configs` aparecem no Table Editor

## 4) Atualizar credenciais no index.html
- Abra `index.html` no editor
- Localize a linha: `const SUPABASE_URL = 'https://YOUR_PROJECT_ID.supabase.co'`
- Substitua com seu `Project URL` do Supabase (Settings → API)
- Localize: `const SUPABASE_ANON_KEY = 'YOUR_ANON_KEY'`
- Substitua com sua `anon` key pública (Settings → API)

## 5) Testando localmente
```bash
# Opção 1: Servir via Python (simples)
cd c:\estoque-banca
python -m http.server 8000

# Opção 2: Servir via Node (recomendado)
npm install -g http-server
cd c:\estoque-banca
http-server

# Depois acesse: http://localhost:8000 ou http://localhost:8080
```

## 6) Testar fluxo de auth + sync
- Abra http://localhost:8000 no navegador
- Clique botão "ENTRAR" (fará redirect para OAuth Google/Github)
- Após login, clique "SINCRONIZAR" → OK para enviar dados locais ao Supabase
- Verifique no Dashboard → Table Editor se os dados chegaram

## 7) Regras de segurança
- Nunca exponha `service_role` key no client
- RLS garante que cada usuário vê apenas seus próprios dados
- O `localStorage` é fallback se offline; sincroniza ao conectar novamente

## 8) Fluxo de dados
```
Local (index.html, localStorage)
    ↓
   [ENTRAR] → OAuth login
    ↓
Supabase Auth (JWT token criado)
    ↓
[SINCRONIZAR] → upsert products/sales/configs com owner=user.id
    ↓
Supabase Database (RLS protege cada linha)
    ↓
Próximas aberturas carregam do Supabase automaticamente
```

## 9) Próximos passos (opcional)
- Criar backend Node/Express para operações sensíveis (service_role key)
- Adicionar Edge Functions para lógica complexa server-side
- Backup e export de dados via script admin

**Importante:** Se receber erro "Could not read localStorage", o navegador pode estar em modo privado/sandbox — use uma abas normal ou configure CORS no Supabase.
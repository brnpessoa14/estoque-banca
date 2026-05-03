# PDV Banca de Jornal

Sistema de Ponto de Venda para Bancas com suporte a estoque, relatórios, PIX QR Code e sincronização com Supabase.

## 🚀 Início Rápido

### Opção 1: Executar Offline (localStorage apenas)

**Sem Supabase** - dados salvos apenas no navegador (útil para teste rápido):

```bash
# Windows: abrir em PowerShell
cd c:\estoque-banca
# Depois abra index.html no navegador (duplo clique ou arraste para o navegador)
```

Ou use um servidor local:

```bash
# Python 3
python -m http.server 8000

# Depois acesse: http://localhost:8000
```

### Opção 2: Com Supabase (recomendado para produção)

1. **Criar projeto Supabase**: https://app.supabase.com → New project

2. **Configurar banco de dados**:
   - Dashboard → SQL Editor → New Query
   - Cole o conteúdo de `supabase-setup.sql` e execute

3. **Configurar OAuth**:
   - Dashboard → Authentication → Providers → Google (ou GitHub)
   - Configure credenciais e adicione redirect URL

4. **Atualizar credenciais**:
   - Abra `index.html` no editor
   - Localize (linhas ~780):
     ```javascript
     const SUPABASE_URL = 'https://YOUR_PROJECT_ID.supabase.co'
     const SUPABASE_ANON_KEY = 'YOUR_ANON_KEY'
     ```
   - Substitua com valores do seu Dashboard → Settings → API

5. **Executar**:
   ```bash
   cd c:\estoque-banca
   npm install  # Instala dependências (http-server, Supabase JS)
   npm run serve  # Abre servidor em http://localhost:8000
   ```

6. **Testar**:
   - Clique **ENTRAR** para fazer login com Google/GitHub
   - Clique **SINCRONIZAR** → OK para enviar dados locais ao Supabase
   - Dashboard Supabase → Table Editor → verifique dados sincronizados

## 📋 Funcionalidades

- ✅ **Carrinho de vendas** — adicione/remova produtos
- ✅ **Categorias** — organize produtos por tipo
- ✅ **Estoque** — controle quantidades e alertas
- ✅ **PIX QR Code** — gere QR Code com valor da venda
- ✅ **Relatórios** — vendas por período, produtos top, histórico
- ✅ **Configurações** — nome banca, chave PIX, cidade
- ✅ **Auth OAuth** — login seguro com Supabase (Supabase apenas)
- ✅ **Sincronização** — localStorage ↔ Supabase (Supabase apenas)

## 🔐 Segurança

- **Offline**: dados salvos em `localStorage` (não sincronizado)
- **Online**: usa `anon` key (segura), RLS protege dados por usuário
- **Nunca** coloque `service_role` no client

## 📁 Estrutura

```
index.html                      # App SPA (tudo em um arquivo)
supabase-setup.sql              # SQL para criar tabelas + RLS
supabase-browser.js             # Helpers de auth/sync (alternativa ao integrado)
supabase-client-example.js      # Exemplos de uso das APIs
SUPABASE_README.md              # Guia detalhado Supabase
package.json                    # Dependências (Node/npm)
```

## 💡 Modo Offline vs Online

| Recurso | Offline | Online (Supabase) |
|---------|---------|-------------------|
| Vender | ✅ | ✅ |
| Estoque | ✅ | ✅ |
| PIX | ✅ | ✅ |
| Login | ❌ | ✅ |
| Sincronização | ❌ | ✅ |
| RLS / Isolamento | ❌ | ✅ |
| Backup Automático | ❌ | ✅ |

## 🐛 Troubleshooting

**"Supabase não está configurado"**
- Verifique se `SUPABASE_URL` e `SUPABASE_ANON_KEY` estão preenchidos em `index.html`
- Se não quiser Supabase, ignore — o app funciona com `localStorage` normalmente

**"Erro ao entrar (OAuth)"**
- Verifique se Google/GitHub OAuth está configurado no Supabase
- Teste redirect URL: deve ser `https://YOUR_PROJECT_ID.supabase.co/auth/v1/callback`

**"Dados não sincronizam"**
- Verifique políticas RLS em `supabase-setup.sql`
- Confirme que o usuário está logado (botão deve dizer "SAIR")
- Abra DevTools (F12) → Console para erros detalhados

## 📞 Suporte

Consulte `SUPABASE_README.md` para guia passo a passo ou abra o console do navegador (F12) para logs.

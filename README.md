# Banca Fácil

Sistema de frente de caixa, estoque e relatórios para bancas. Pode ser usado localmente com Python e SQLite ou publicado no Vercel com Python Functions e PostgreSQL Neon. A aplicação inclui autenticação e isolamento completo dos dados por conta.

**Produção:** [estoque-banca.vercel.app](https://estoque-banca.vercel.app)

## Começar

Requisito: Python 3.9 ou superior.

```bash
python3 start.py
```

O navegador abre em `http://127.0.0.1:8000`. No Windows, também é possível executar `start.bat`.

### Conta de demonstração

- E-mail: `cliente@bancafacil.com.br`
- Senha: `Cliente@123`

A conta é criada automaticamente na primeira inicialização, junto com seis produtos de exemplo. Para uma instalação real, entre na conta demo e troque a senha em **Configurações**, ou crie uma conta separada pela tela inicial.

## Funcionalidades

- Cadastro e login com sessão protegida por cookie HttpOnly;
- dados completamente isolados por conta;
- catálogo com busca, categorias e alerta de estoque;
- carrinho com controle de quantidade e validação do saldo disponível;
- fechamento por PIX, dinheiro, débito ou crédito;
- baixa de estoque e gravação da venda em uma única transação;
- cadastro, edição e exclusão de produtos;
- QR Code e código PIX Copia e Cola;
- indicadores diários, ranking, histórico e auditoria;
- filtro por período e exportação de vendas em CSV;
- configurações da banca, PIX e WhatsApp;
- alteração segura de senha;
- interface responsiva para computador, tablet e celular.

## Bancos de dados

No uso local, o SQLite é inicializado automaticamente em `data/banca.sqlite3`. No Vercel, a função em `api/index.py` usa PostgreSQL Neon pela variável secreta `DATABASE_URL`. Os dois schemas contêm usuários, sessões, produtos, vendas, itens, configurações e atividades. Senhas usam PBKDF2-HMAC-SHA256 com salt individual; tokens de sessão são aleatórios e somente o hash é persistido.

O arquivo do banco não é versionado para evitar publicar dados de clientes. Para fazer backup:

1. encerre o servidor;
2. copie `data/banca.sqlite3` para um local seguro;
3. para restaurar, devolva a cópia ao mesmo caminho antes de iniciar.

É possível escolher outro arquivo:

```bash
python3 start.py --db /caminho/seguro/minha-banca.sqlite3
```

## Testes

```bash
python3 -m unittest discover -s tests -v
```

Os testes cobrem saúde da API, proteção de rotas, conta demo, credenciais inválidas, criação de conta, CRUD de produto, venda e baixa transacional, estoque insuficiente, isolamento entre clientes, configurações, troca de senha e logout. O teste PostgreSQL é executado quando `DATABASE_URL` está definida.

## Deploy no Vercel

O projeto já contém `vercel.json`, build restrito aos arquivos públicos e API Python serverless. O PostgreSQL deve estar conectado aos ambientes Development, Preview e Production.

```bash
vercel pull
vercel deploy          # preview
vercel deploy --prod   # produção manual
```

O fluxo normal é fazer push de uma branch, validar o preview e mesclar na `main`; a integração Git do Vercel publica a produção automaticamente. Consulte o passo a passo e a manutenção do banco em [DOCUMENTACAO.md](DOCUMENTACAO.md#18-publicação-e-produção).

## Opções do servidor

```bash
python3 start.py --help
python3 start.py --no-browser
python3 start.py --port 9000
```

Por segurança, o servidor escuta somente em `127.0.0.1` por padrão e expõe apenas os três arquivos públicos da interface. Para acesso em rede, use `--host 0.0.0.0` apenas em uma rede confiável. Uma publicação na internet exige proxy reverso com HTTPS, monitoramento e estratégia de backup.

## Estrutura

```text
index.html          Interface e estrutura das telas
styles.css          Sistema visual e responsividade
app.js              Estado da interface e integração com a API
start.py            Servidor HTTP, API, autenticação e SQLite
api/index.py        Function serverless e adaptação PostgreSQL
vercel.json         Build, rotas, região e cabeçalhos de segurança
build.mjs           Gera o diretório público do deploy
requirements.txt    Dependência Python do PostgreSQL
tests/              Testes SQLite e PostgreSQL
start.bat           Inicialização no Windows
```

Consulte [QUICKSTART.md](QUICKSTART.md) para um roteiro curto de primeira utilização e [DOCUMENTACAO.md](DOCUMENTACAO.md) para instalação, arquitetura, banco, API, segurança, backup, testes, produção e solução de problemas.

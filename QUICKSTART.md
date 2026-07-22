# Início rápido

Produção: [https://estoque-banca.vercel.app](https://estoque-banca.vercel.app). Os passos abaixo também permitem executar uma instalação local independente.

## 1. Inicie o sistema

macOS ou Linux:

```bash
python3 start.py
```

Windows:

```bat
start.bat
```

Não abra `index.html` diretamente: cadastro, login e banco dependem do servidor iniciado por `start.py`.

## 2. Faça o primeiro acesso

Use a conta pronta:

```text
E-mail: cliente@bancafacil.com.br
Senha:  Cliente@123
```

Também é possível selecionar **Criar conta** e cadastrar outro cliente. Cada conta enxerga apenas os próprios produtos e vendas.

## 3. Prepare a banca

1. Abra **Configurações**.
2. Informe o nome da banca, recebedor, cidade e chave PIX.
3. Se for usar a conta demo em operação, altere a senha.
4. Abra **Produtos e estoque** para revisar ou cadastrar itens.
5. Volte a **Frente de caixa** e registre uma venda de teste.

## Soluções rápidas

- Porta ocupada: execute `python3 start.py --port 9000`.
- Navegador não abriu: acesse `http://127.0.0.1:8000`.
- Esqueceu uma senha criada por você: restaure um backup do banco ou crie outra conta; senhas não podem ser recuperadas em texto puro.
- Banco local: o arquivo fica em `data/banca.sqlite3` e é criado automaticamente.
- Banco online: PostgreSQL Neon, configurado no Vercel por `DATABASE_URL`.
- Testes: execute `python3 -m unittest discover -s tests -v`.

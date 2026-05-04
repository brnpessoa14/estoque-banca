-- Supabase setup SQL
-- Execute este script no editor SQL do Supabase (Dashboard -> SQL)
-- Recomendado: habilitar extensão pgcrypto para gen_random_uuid()

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Tabela: products
CREATE TABLE IF NOT EXISTS products (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  owner uuid REFERENCES auth.users(id) NOT NULL,
  name text NOT NULL,
  category text,
  price numeric(10,2) NOT NULL DEFAULT 0,
  stock integer DEFAULT 0,
  min_stock integer DEFAULT 0,
  created_at timestamptz DEFAULT now()
);

-- Tabela: sales
CREATE TABLE IF NOT EXISTS sales (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  owner uuid REFERENCES auth.users(id) NOT NULL,
  date timestamptz DEFAULT now(),
  items jsonb NOT NULL,
  total numeric(12,2) NOT NULL,
  payment_method text
);

-- Tabela: configs (um registro por usuário)
CREATE TABLE IF NOT EXISTS configs (
  owner uuid REFERENCES auth.users(id) PRIMARY KEY,
  bank_name text,
  merchant_name text,
  city text,
  pix_key text,
  whatsapp_number text
);

-- Tabela: activity_logs
CREATE TABLE IF NOT EXISTS activity_logs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  owner uuid REFERENCES auth.users(id) NOT NULL,
  date timestamptz DEFAULT now(),
  type text NOT NULL,
  message text NOT NULL,
  meta jsonb DEFAULT '{}'::jsonb
);

-- Habilitar RLS e políticas por tabela
ALTER TABLE products ENABLE ROW LEVEL SECURITY;
ALTER TABLE sales ENABLE ROW LEVEL SECURITY;
ALTER TABLE configs ENABLE ROW LEVEL SECURITY;
ALTER TABLE activity_logs ENABLE ROW LEVEL SECURITY;

-- Política: permitir ao usuário autenticado gerenciar suas próprias linhas
CREATE POLICY "products_owner_policy" ON products
  FOR ALL
  TO authenticated
  USING (owner = auth.uid())
  WITH CHECK (owner = auth.uid());

CREATE POLICY "sales_owner_policy" ON sales
  FOR ALL
  TO authenticated
  USING (owner = auth.uid())
  WITH CHECK (owner = auth.uid());

CREATE POLICY "configs_owner_policy" ON configs
  FOR ALL
  TO authenticated
  USING (owner = auth.uid())
  WITH CHECK (owner = auth.uid());

CREATE POLICY "activity_logs_owner_policy" ON activity_logs
  FOR ALL
  TO authenticated
  USING (owner = auth.uid())
  WITH CHECK (owner = auth.uid());

-- Observações:
-- 1) Insira o campo `owner` nos INSERTs com o `auth.uid()` do contexto (client-side Supabase faz isso quando o usuário está autenticado).
-- 2) Para operações administrativas (ex.: migração em massa, relatórios globais), use uma função server-side protegida com a `service_role` key (NUNCA coloque service_role no client).
-- 3) Teste as políticas criando um usuário de teste via Supabase Auth e executando SELECT/INSERT/UPDATE/DELETE via o painel SQL com a sessão apropriada.

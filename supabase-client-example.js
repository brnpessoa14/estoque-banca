// Exemplo mínimo de uso do Supabase no client (substitua URL e ANON KEY)
// Instalar: npm install @supabase/supabase-js

import { createClient } from '@supabase/supabase-js'

const SUPABASE_URL = 'https://YOUR_PROJECT_ID.supabase.co'
const SUPABASE_ANON_KEY = 'YOUR_ANON_KEY' // pública - permitida no client

export const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY)

// Autenticação OAuth (redireciona para provedor)
export async function signInWithProvider(provider = 'google') {
  const { data, error } = await supabase.auth.signInWithOAuth({ provider })
  if (error) console.error('login error', error)
  return data
}

// Observa mudanças de autenticação
supabase.auth.onAuthStateChange((event, session) => {
  console.log('auth event', event)
  // session?.access_token contém token JWT que o supabase usa para autorizar requests
})

export async function getCurrentUserId() {
  const { data } = await supabase.auth.getUser()
  return data?.user?.id || null
}

// Buscar produtos do usuário autenticado
export async function fetchProducts() {
  const userId = await getCurrentUserId()
  if (!userId) return []
  const { data, error } = await supabase
    .from('products')
    .select('*')
    .eq('owner', userId)
    .order('created_at', { ascending: false })

  if (error) {
    console.error(error)
    return []
  }
  return data
}

// Inserir produto atribuído ao owner atual
export async function insertProduct(product) {
  const userId = await getCurrentUserId()
  if (!userId) throw new Error('Usuário não autenticado')
  const { data, error } = await supabase.from('products').insert([{ ...product, owner: userId }])
  if (error) throw error
  return data
}

// Inserir venda (items como JSON)
export async function insertSale(sale) {
  const userId = await getCurrentUserId()
  if (!userId) throw new Error('Usuário não autenticado')
  const { data, error } = await supabase.from('sales').insert([{ ...sale, owner: userId }])
  if (error) throw error
  return data
}

// Exemplo de sincronização local->server (simples)
export async function syncLocalProducts(localProducts) {
  const userId = await getCurrentUserId()
  if (!userId) return
  // implementação simples: enviar cada produto com owner=userId
  for (const p of localProducts) {
    await supabase.from('products').upsert({ ...p, owner: userId })
  }
}

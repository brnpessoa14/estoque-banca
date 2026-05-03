// supabase-browser.js
// Substitua as constantes abaixo com seu Project URL e anon key do Supabase
const SUPABASE_URL = 'https://YOUR_PROJECT_ID.supabase.co'
const SUPABASE_ANON_KEY = 'YOUR_ANON_KEY'

const supabaseClient = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY)

async function signIn() {
  // redireciona para provedor OAuth (padrão: google)
  await supabaseClient.auth.signInWithOAuth({ provider: 'google' })
}

async function signOut() {
  await supabaseClient.auth.signOut()
  window.showToast && window.showToast('Desconectado')
}

async function getUser() {
  try {
    const { data } = await supabaseClient.auth.getUser()
    return data?.user || null
  } catch (e) {
    return null
  }
}

async function updateAuthUI() {
  const btnAuth = document.getElementById('btnAuth')
  const btnSync = document.getElementById('btnSync')
  const user = await getUser()
  if (!btnAuth || !btnSync) return
  if (user) {
    btnAuth.textContent = 'SAIR'
    btnSync.disabled = false
  } else {
    btnAuth.textContent = 'ENTRAR'
    btnSync.disabled = true
  }
}

// Sincroniza os dados locais (localStorage) para Supabase
async function syncLocalToSupabase() {
  const user = await getUser()
  if (!user) {
    window.showToast && window.showToast('Faça login antes de sincronizar')
    return
  }

  const productsRaw = localStorage.getItem('pdv_banca_products')
  const salesRaw = localStorage.getItem('pdv_banca_sales')
  const configRaw = localStorage.getItem('pdv_banca_config')

  try {
    if (productsRaw) {
      const products = JSON.parse(productsRaw)
      for (const p of products) {
        // upsert por id; mantém id local (uuid)
        await supabaseClient.from('products').upsert({ ...p, owner: user.id })
      }
    }

    if (salesRaw) {
      const sales = JSON.parse(salesRaw)
      for (const s of sales) {
        await supabaseClient.from('sales').upsert({ ...s, owner: user.id })
      }
    }

    if (configRaw) {
      const cfg = JSON.parse(configRaw)
      await supabaseClient.from('configs').upsert({ ...cfg, owner: user.id })
    }

    window.showToast && window.showToast('Sincronização concluída')
  } catch (err) {
    console.error('sync error', err)
    window.showToast && window.showToast('Erro ao sincronizar. Veja console.')
  }
}

// Puxa dados do Supabase para o local (substitui o estado salvo no navegador)
async function fetchRemoteToLocal() {
  const user = await getUser()
  if (!user) {
    window.showToast && window.showToast('Faça login antes de sincronizar')
    return
  }

  try {
    const { data: products } = await supabaseClient.from('products').select('*').eq('owner', user.id)
    const { data: sales } = await supabaseClient.from('sales').select('*').eq('owner', user.id)
    const { data: configs } = await supabaseClient.from('configs').select('*').eq('owner', user.id)

    if (products) localStorage.setItem('pdv_banca_products', JSON.stringify(products))
    if (sales) localStorage.setItem('pdv_banca_sales', JSON.stringify(sales))
    if (configs && configs.length) localStorage.setItem('pdv_banca_config', JSON.stringify(configs[0]))

    window.showToast && window.showToast('Dados remotos baixados para o navegador')
    // recarrega a aplicação (simples) para refletir os dados
    window.location.reload()
  } catch (err) {
    console.error('fetch error', err)
    window.showToast && window.showToast('Erro ao puxar dados. Veja console.')
  }
}

// Bind dos botões adicionados no index.html
window.addEventListener('DOMContentLoaded', () => {
  const btnAuth = document.getElementById('btnAuth')
  const btnSync = document.getElementById('btnSync')

  if (btnAuth) {
    btnAuth.addEventListener('click', async () => {
      const user = await getUser()
      if (user) {
        await signOut()
        updateAuthUI()
      } else {
        await signIn()
      }
    })
  }

  if (btnSync) {
    btnSync.addEventListener('click', async () => {
      // mostra opções: enviar -> usar syncLocalToSupabase, baixar -> fetchRemoteToLocal
      const choice = confirm('OK = enviar dados locais para Supabase. Cancel = baixar dados do Supabase para o navegador.')
      if (choice) await syncLocalToSupabase()
      else await fetchRemoteToLocal()
    })
  }

  // atualiza UI inicial
  updateAuthUI()
})

// Observa mudanças de estado de autenticação
supabaseClient.auth.onAuthStateChange(() => {
  updateAuthUI()
})

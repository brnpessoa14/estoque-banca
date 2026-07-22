"use strict";

const DEMO = { email: "cliente@bancafacil.com.br", password: "Cliente@123" };
const moneyFormatter = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
const dateFormatter = new Intl.DateTimeFormat("pt-BR", { dateStyle: "medium", timeStyle: "short" });

const state = {
  user: null,
  products: [],
  sales: [],
  settings: {},
  activities: [],
  summary: {},
  cart: new Map(),
  category: "Todos",
  view: "sale",
  reportStart: "",
  reportEnd: "",
};

const $ = (selector, parent = document) => parent.querySelector(selector);
const $$ = (selector, parent = document) => [...parent.querySelectorAll(selector)];

document.addEventListener("DOMContentLoaded", initialize);

async function initialize() {
  bindAuth();
  bindApplication();
  setCurrentDate();
  setReportDefaults();
  setLoading(true);
  try {
    await api("/api/auth/me");
    await enterApplication();
  } catch (error) {
    showAuth();
    if (error.status && error.status !== 401) toast(error.message, "error");
  } finally {
    setLoading(false);
  }
}

function bindAuth() {
  $("#loginTab").addEventListener("click", () => setAuthMode("login"));
  $("#registerTab").addEventListener("click", () => setAuthMode("register"));
  $("#loginForm").addEventListener("submit", login);
  $("#registerForm").addEventListener("submit", register);
  $("#demoAccess").addEventListener("click", demoLogin);
  $$('[data-password-toggle]').forEach((button) => {
    button.addEventListener("click", () => {
      const input = $("input", button.parentElement);
      const visible = input.type === "text";
      input.type = visible ? "password" : "text";
      button.textContent = visible ? "Mostrar" : "Ocultar";
      button.setAttribute("aria-label", visible ? "Mostrar senha" : "Ocultar senha");
    });
  });
}

function bindApplication() {
  $$('[data-view]').forEach((button) => button.addEventListener("click", () => switchView(button.dataset.view)));
  $("#logoutButton").addEventListener("click", logout);
  $("#menuButton").addEventListener("click", openSidebar);
  $("#sidebarBackdrop").addEventListener("click", closeSidebar);
  $("#catalogSearch").addEventListener("input", renderCatalog);
  $("#inventorySearch").addEventListener("input", renderInventory);
  $("#stockFilter").addEventListener("change", renderInventory);
  $("#clearCartButton").addEventListener("click", clearCart);
  $("#checkoutButton").addEventListener("click", openCheckout);
  $("#addProductButton").addEventListener("click", () => openProductForm());
  $("#reportStart").addEventListener("change", renderReports);
  $("#reportEnd").addEventListener("change", renderReports);
  $("#exportButton").addEventListener("click", exportSales);
  $("#businessForm").addEventListener("submit", saveSettings);
  $("#passwordForm").addEventListener("submit", changePassword);
  $("#modalClose").addEventListener("click", closeModal);
  $("#appModal").addEventListener("click", (event) => {
    if (event.target === event.currentTarget) closeModal();
  });
}

function setAuthMode(mode) {
  const registering = mode === "register";
  $("#loginTab").classList.toggle("active", !registering);
  $("#registerTab").classList.toggle("active", registering);
  $("#loginTab").setAttribute("aria-selected", String(!registering));
  $("#registerTab").setAttribute("aria-selected", String(registering));
  $("#loginForm").classList.toggle("hidden", registering);
  $("#registerForm").classList.toggle("hidden", !registering);
  $("#authTitle").textContent = registering ? "Comece agora" : "Bem-vindo de volta";
  $("#authSubtitle").textContent = registering
    ? "Crie sua conta e tenha um espaço exclusivo para sua banca."
    : "Entre para acessar sua banca e continuar vendendo.";
}

async function login(event) {
  event.preventDefault();
  const form = event.currentTarget;
  await submitAuth(form, "/api/auth/login", "Entrando...");
}

async function register(event) {
  event.preventDefault();
  const form = event.currentTarget;
  await submitAuth(form, "/api/auth/register", "Criando conta...");
}

async function submitAuth(form, endpoint, pendingText) {
  const button = $('button[type="submit"]', form);
  const original = button.innerHTML;
  button.disabled = true;
  button.textContent = pendingText;
  try {
    await api(endpoint, { method: "POST", data: Object.fromEntries(new FormData(form)) });
    form.reset();
    await enterApplication();
  } catch (error) {
    toast(error.message, "error");
  } finally {
    button.disabled = false;
    button.innerHTML = original;
  }
}

async function demoLogin() {
  const button = $("#demoAccess");
  button.disabled = true;
  try {
    await api("/api/auth/login", { method: "POST", data: DEMO });
    await enterApplication();
    toast("Conta de demonstração carregada.");
  } catch (error) {
    toast(error.message, "error");
  } finally {
    button.disabled = false;
  }
}

async function logout() {
  try { await api("/api/auth/logout", { method: "POST", data: {} }); } catch (_) { /* sessão local será descartada */ }
  state.user = null;
  state.cart.clear();
  showAuth();
  toast("Você saiu da conta.");
}

async function enterApplication() {
  setLoading(true);
  try {
    await loadData();
    $("#authScreen").classList.add("hidden");
    $("#appScreen").classList.remove("hidden");
    renderAll();
  } finally {
    setLoading(false);
  }
}

function showAuth() {
  $("#appScreen").classList.add("hidden");
  $("#authScreen").classList.remove("hidden");
  setAuthMode("login");
}

async function loadData() {
  const data = await api("/api/bootstrap");
  state.user = data.user;
  state.products = data.products || [];
  state.sales = data.sales || [];
  state.settings = data.settings || {};
  state.activities = data.activities || [];
  state.summary = data.summary || {};
  for (const [productId, quantity] of state.cart) {
    const product = state.products.find((item) => item.id === productId);
    if (!product || product.stock === 0) state.cart.delete(productId);
    else if (quantity > product.stock) state.cart.set(productId, product.stock);
  }
}

function renderAll() {
  renderIdentity();
  renderSummary();
  renderCatalog();
  renderCart();
  renderInventory();
  renderReports();
  fillSettings();
}

function renderIdentity() {
  const name = state.user?.name || "Cliente";
  const business = state.settings.businessName || "Minha Banca";
  $("#userName").textContent = name;
  $("#userEmail").textContent = state.user?.email || "";
  $("#userAvatar").textContent = name.charAt(0).toUpperCase();
  $("#sidebarBusiness").textContent = business;
  document.title = `${business} — Banca Fácil`;
}

function renderSummary() {
  const localToday = toInputDate(new Date());
  const todaySales = state.sales.filter((sale) => toInputDate(new Date(sale.createdAt)) === localToday);
  const revenue = todaySales.reduce((sum, sale) => sum + sale.total, 0);
  const items = state.products.reduce((sum, product) => sum + product.stock, 0);
  const low = state.products.filter((product) => product.stock <= product.minStock).length;
  $("#todayRevenue").textContent = money(revenue);
  $("#todaySales").textContent = plural(todaySales.length, "atendimento", "atendimentos");
  $("#stockCount").textContent = String(items);
  $("#lowStockCount").textContent = String(low);
  $("#lowStockBadge").textContent = String(low);
  $("#productMetric").textContent = String(state.products.length);
  $("#inventoryValueMetric").textContent = money(state.products.reduce((sum, product) => sum + product.price * product.stock, 0));
  $("#lowMetric").textContent = String(low);
}

function renderCatalog() {
  const categories = ["Todos", ...new Set(state.products.map((product) => product.category).filter(Boolean))];
  if (!categories.includes(state.category)) state.category = "Todos";
  $("#categoryList").innerHTML = categories.map((category) =>
    `<button class="category-chip${state.category === category ? " active" : ""}" type="button" data-category="${escapeHtml(category)}">${escapeHtml(category)}</button>`
  ).join("");
  $$('[data-category]', $("#categoryList")).forEach((button) => button.addEventListener("click", () => {
    state.category = button.dataset.category;
    renderCatalog();
  }));

  const term = normalize($("#catalogSearch").value);
  const products = state.products.filter((product) => {
    const categoryMatches = state.category === "Todos" || product.category === state.category;
    const textMatches = normalize(`${product.name} ${product.category} ${product.barcode}`).includes(term);
    return categoryMatches && textMatches;
  });
  const grid = $("#productGrid");
  if (!products.length) {
    grid.innerHTML = emptyState("⌕", "Nenhum produto encontrado", state.products.length ? "Tente outra busca ou categoria." : "Cadastre o primeiro produto na área de estoque.");
    return;
  }
  grid.innerHTML = products.map((product) => {
    const status = stockStatus(product);
    return `<button class="product-card" type="button" data-add-product="${product.id}" ${product.stock <= 0 ? "disabled" : ""}>
      <span class="product-category">${escapeHtml(product.category)}</span>
      <h3>${escapeHtml(product.name)}</h3>
      <span class="stock-line"><span class="stock-pill ${status.className}">${status.label}</span></span>
      <footer><strong>${money(product.price)}</strong><span class="add-dot" aria-hidden="true">+</span></footer>
    </button>`;
  }).join("");
  $$('[data-add-product]', grid).forEach((button) => button.addEventListener("click", () => addToCart(button.dataset.addProduct)));
}

function addToCart(productId) {
  const product = getProduct(productId);
  if (!product || product.stock <= 0) return;
  const current = state.cart.get(productId) || 0;
  if (current >= product.stock) {
    toast("Não há mais unidades disponíveis deste produto.", "error");
    return;
  }
  state.cart.set(productId, current + 1);
  renderCart();
}

function changeCartQuantity(productId, delta) {
  const product = getProduct(productId);
  const current = state.cart.get(productId) || 0;
  const next = current + delta;
  if (next <= 0) state.cart.delete(productId);
  else if (product && next <= product.stock) state.cart.set(productId, next);
  else toast("Quantidade maior que o estoque disponível.", "error");
  renderCart();
}

function clearCart() {
  if (!state.cart.size) return;
  state.cart.clear();
  renderCart();
}

function cartItems() {
  return [...state.cart.entries()].map(([productId, quantity]) => ({ product: getProduct(productId), quantity })).filter((item) => item.product);
}

function cartTotal() {
  return cartItems().reduce((sum, item) => sum + item.product.price * item.quantity, 0);
}

function renderCart() {
  const items = cartItems();
  const count = items.reduce((sum, item) => sum + item.quantity, 0);
  $("#cartCount").textContent = count ? plural(count, "item", "itens") : "Nenhum item";
  $("#cartTotal").textContent = money(cartTotal());
  $("#checkoutButton").disabled = !items.length;
  $("#clearCartButton").classList.toggle("hidden", !items.length);
  const list = $("#cartList");
  if (!items.length) {
    list.innerHTML = `<div class="cart-empty"><span aria-hidden="true">▤</span><strong>Carrinho vazio</strong><p>Clique em um produto para iniciar a venda.</p></div>`;
    return;
  }
  list.innerHTML = items.map(({ product, quantity }) => `<article class="cart-item">
    <div><h4>${escapeHtml(product.name)}</h4><small>${money(product.price)} por unidade</small>
      <div class="quantity-control"><button type="button" data-cart-minus="${product.id}" aria-label="Diminuir ${escapeHtml(product.name)}">−</button><span>${quantity}</span><button type="button" data-cart-plus="${product.id}" aria-label="Aumentar ${escapeHtml(product.name)}">+</button></div>
    </div><strong>${money(product.price * quantity)}</strong>
  </article>`).join("");
  $$('[data-cart-minus]', list).forEach((button) => button.addEventListener("click", () => changeCartQuantity(button.dataset.cartMinus, -1)));
  $$('[data-cart-plus]', list).forEach((button) => button.addEventListener("click", () => changeCartQuantity(button.dataset.cartPlus, 1)));
}

function renderInventory() {
  const term = normalize($("#inventorySearch").value);
  const filter = $("#stockFilter").value;
  const products = state.products.filter((product) => {
    const textMatches = normalize(`${product.name} ${product.category} ${product.barcode}`).includes(term);
    const stockMatches = filter === "all"
      || (filter === "low" && product.stock <= product.minStock)
      || (filter === "available" && product.stock > product.minStock)
      || (filter === "out" && product.stock === 0);
    return textMatches && stockMatches;
  });
  const body = $("#inventoryTable");
  if (!products.length) {
    body.innerHTML = `<tr><td colspan="6"><div class="empty-state"><strong>Nenhum produto neste filtro</strong><p>Altere a busca ou cadastre um novo item.</p></div></td></tr>`;
    return;
  }
  body.innerHTML = products.map((product) => {
    const status = stockStatus(product);
    return `<tr>
      <td><strong>${escapeHtml(product.name)}</strong><small>${product.barcode ? `Cód. ${escapeHtml(product.barcode)}` : "Sem código de barras"}</small></td>
      <td>${escapeHtml(product.category)}</td><td><strong>${money(product.price)}</strong></td>
      <td><strong>${product.stock} un.</strong><small>Mínimo: ${product.minStock}</small></td>
      <td><span class="stock-pill ${status.className}">${status.label}</span></td>
      <td><div class="table-actions"><button class="mini-button" type="button" data-edit-product="${product.id}">Editar</button><button class="mini-button danger" type="button" data-delete-product="${product.id}">Excluir</button></div></td>
    </tr>`;
  }).join("");
  $$('[data-edit-product]', body).forEach((button) => button.addEventListener("click", () => openProductForm(getProduct(button.dataset.editProduct))));
  $$('[data-delete-product]', body).forEach((button) => button.addEventListener("click", () => confirmDeleteProduct(getProduct(button.dataset.deleteProduct))));
}

function openProductForm(product = null) {
  const editing = Boolean(product);
  const content = document.createElement("form");
  content.className = "form-stack";
  content.innerHTML = `<div class="form-grid two">
    <label class="field-group full"><span>Nome do produto</span><input name="name" value="${escapeHtml(product?.name || "")}" minlength="2" maxlength="100" required autofocus></label>
    <label class="field-group"><span>Categoria</span><input name="category" value="${escapeHtml(product?.category || "")}" minlength="2" maxlength="50" placeholder="Ex.: Bebidas" required></label>
    <label class="field-group"><span>Código de barras</span><input name="barcode" value="${escapeHtml(product?.barcode || "")}" maxlength="40" inputmode="numeric"></label>
    <label class="field-group"><span>Preço de venda</span><input name="price" type="number" min="0" max="1000000" step="0.01" value="${product?.price ?? ""}" required></label>
    <label class="field-group"><span>Estoque atual</span><input name="stock" type="number" min="0" max="1000000" step="1" value="${product?.stock ?? 0}" required></label>
    <label class="field-group"><span>Alerta de estoque mínimo</span><input name="minStock" type="number" min="0" max="1000000" step="1" value="${product?.minStock ?? 0}" required></label>
  </div><div class="modal-actions"><button class="btn btn-primary" type="submit">${editing ? "Salvar alterações" : "Adicionar produto"}</button></div>`;
  openModal(editing ? "EDITAR PRODUTO" : "NOVO PRODUTO", editing ? "Atualizar produto" : "Cadastrar produto", editing ? "Revise as informações do estoque." : "Preencha os dados para disponibilizar o item no caixa.", content);
  content.addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = $('button[type="submit"]', content);
    button.disabled = true;
    try {
      const data = Object.fromEntries(new FormData(content));
      await api(editing ? `/api/products/${product.id}` : "/api/products", { method: editing ? "PATCH" : "POST", data });
      await loadData();
      renderAll();
      closeModal();
      toast(editing ? "Produto atualizado." : "Produto cadastrado.");
    } catch (error) {
      toast(error.message, "error");
    } finally { button.disabled = false; }
  });
}

function confirmDeleteProduct(product) {
  if (!product) return;
  const content = document.createElement("div");
  content.innerHTML = `<p class="confirm-copy">Deseja excluir <strong>${escapeHtml(product.name)}</strong>? O histórico das vendas anteriores será preservado.</p><div class="modal-actions"><button class="btn btn-soft" type="button" data-cancel>Cancelar</button><button class="btn btn-danger" type="button" data-confirm>Excluir produto</button></div>`;
  openModal("AÇÃO IRREVERSÍVEL", "Excluir produto", "Confirme antes de continuar.", content);
  $('[data-cancel]', content).addEventListener("click", closeModal);
  $('[data-confirm]', content).addEventListener("click", async (event) => {
    event.currentTarget.disabled = true;
    try {
      await api(`/api/products/${product.id}`, { method: "DELETE", data: {} });
      state.cart.delete(product.id);
      await loadData();
      renderAll();
      closeModal();
      toast("Produto excluído.");
    } catch (error) { toast(error.message, "error"); }
  });
}

function openCheckout() {
  if (!state.cart.size) return;
  const content = document.createElement("div");
  content.innerHTML = `<div class="checkout-total"><span>Total a receber</span><strong>${money(cartTotal())}</strong></div><p class="confirm-copy">Selecione como o cliente fará o pagamento:</p><div class="payment-options">
    ${[["pix", "PIX", "Pagamento instantâneo"], ["dinheiro", "Dinheiro", "Recebimento no caixa"], ["debito", "Cartão de débito", "Máquina de cartão"], ["credito", "Cartão de crédito", "Máquina de cartão"]].map(([value, label, help]) => `<button class="payment-option" type="button" data-payment="${value}"><strong>${label}</strong><small>${help}</small></button>`).join("")}
  </div>`;
  openModal("FECHAR VENDA", "Forma de pagamento", "O estoque será atualizado automaticamente.", content);
  $$('[data-payment]', content).forEach((button) => button.addEventListener("click", () => {
    if (button.dataset.payment === "pix") openPixCheckout();
    else finishSale(button.dataset.payment, button);
  }));
}

async function finishSale(paymentMethod, button) {
  button.disabled = true;
  try {
    const data = { paymentMethod, items: cartItems().map((item) => ({ productId: item.product.id, quantity: item.quantity })) };
    const result = await api("/api/sales", { method: "POST", data });
    const total = result.sale.total;
    state.cart.clear();
    await loadData();
    renderAll();
    closeModal();
    toast(`Venda de ${money(total)} registrada com sucesso.`);
  } catch (error) {
    toast(error.message, "error");
    await loadData().catch(() => {});
    renderAll();
    button.disabled = false;
  }
}

function openPixCheckout() {
  if (!state.settings.pixKey) {
    closeModal();
    toast("Cadastre uma chave PIX nas configurações.", "error");
    switchView("settings");
    return;
  }
  const payload = buildPixPayload({
    key: state.settings.pixKey,
    merchantName: state.settings.merchantName || state.settings.businessName,
    city: state.settings.city,
    amount: cartTotal(),
  });
  const content = document.createElement("div");
  content.innerHTML = `<div class="pix-layout"><div class="qr-box" id="pixQr"><span>Gerando QR Code...</span></div><div class="pix-details"><div class="checkout-total"><span>Valor da cobrança</span><strong>${money(cartTotal())}</strong></div><p class="pix-instruction">Apresente o QR Code e confirme o recebimento no aplicativo bancário antes de concluir.</p><p class="pix-copy" id="pixCode">${escapeHtml(payload)}</p><div class="modal-actions pix-actions"><button class="btn btn-soft" type="button" data-copy-pix>Copiar código</button><button class="btn btn-primary" type="button" data-confirm-pix>Pagamento recebido</button></div></div></div>`;
  openModal("COBRANÇA PIX", "Receber com PIX", "A venda só será registrada após sua confirmação.", content, true);
  $('[data-copy-pix]', content).addEventListener("click", async () => {
    try { await navigator.clipboard.writeText(payload); toast("Código PIX copiado."); }
    catch (_) { toast("Selecione e copie o código manualmente.", "error"); }
  });
  $('[data-confirm-pix]', content).addEventListener("click", (event) => finishSale("pix", event.currentTarget));
  const target = $("#pixQr", content);
  target.innerHTML = "";
  if (window.QRCode) {
    new window.QRCode(target, { text: payload, width: 190, height: 190, colorDark: "#0b1f33", colorLight: "#ffffff", correctLevel: window.QRCode.CorrectLevel.M });
  } else {
    target.innerHTML = `<div class="empty-state"><strong>QR indisponível</strong><p>Use o botão para copiar o código PIX.</p></div>`;
  }
}

function renderReports() {
  state.reportStart = $("#reportStart").value;
  state.reportEnd = $("#reportEnd").value;
  const sales = filteredSales();
  const revenue = sales.reduce((sum, sale) => sum + sale.total, 0);
  $("#reportRevenue").textContent = money(revenue);
  $("#reportSales").textContent = String(sales.length);
  $("#reportAverage").textContent = money(sales.length ? revenue / sales.length : 0);
  $("#exportButton").disabled = !sales.length;
  renderPayments(sales, revenue);
  renderRanking(sales);
  renderSalesList(sales);
  renderActivities();
}

function filteredSales() {
  const start = state.reportStart ? new Date(`${state.reportStart}T00:00:00`) : new Date(0);
  const end = state.reportEnd ? new Date(`${state.reportEnd}T23:59:59.999`) : new Date(8640000000000000);
  return state.sales.filter((sale) => {
    const date = new Date(sale.createdAt);
    return date >= start && date <= end;
  });
}

function renderPayments(sales, revenue) {
  const methods = { pix: 0, dinheiro: 0, debito: 0, credito: 0 };
  sales.forEach((sale) => { methods[sale.paymentMethod] = (methods[sale.paymentMethod] || 0) + sale.total; });
  const labels = { pix: "PIX", dinheiro: "Dinheiro", debito: "Débito", credito: "Crédito" };
  $("#paymentBars").innerHTML = Object.entries(methods).map(([method, total]) => {
    const percentage = revenue ? Math.round((total / revenue) * 100) : 0;
    const bucket = Math.max(0, Math.min(100, Math.round(percentage / 10) * 10));
    return `<div class="payment-row"><strong>${labels[method]}</strong><div class="bar-track"><div class="bar-fill width-${bucket}"></div></div><span>${money(total)}</span></div>`;
  }).join("");
}

function renderRanking(sales) {
  const map = new Map();
  sales.forEach((sale) => sale.items.forEach((item) => {
    const current = map.get(item.productId || item.name) || { name: item.name, quantity: 0, total: 0 };
    current.quantity += item.quantity;
    current.total += item.quantity * item.price;
    map.set(item.productId || item.name, current);
  }));
  const ranking = [...map.values()].sort((a, b) => b.quantity - a.quantity).slice(0, 6);
  $("#rankingList").innerHTML = ranking.length ? ranking.map((item, index) => `<div class="ranking-item"><span class="rank-number">${index + 1}</span><div><strong>${escapeHtml(item.name)}</strong><small>${plural(item.quantity, "unidade", "unidades")}</small></div><strong>${money(item.total)}</strong></div>`).join("") : emptyState("↗", "Sem dados no período", "As vendas aparecerão aqui.");
}

function renderSalesList(sales) {
  $("#salesList").innerHTML = sales.length ? sales.slice(0, 10).map((sale) => `<div class="sale-row"><div><strong>${formatPayment(sale.paymentMethod)}</strong><small>${formatDate(sale.createdAt)} · ${plural(sale.items.reduce((sum, item) => sum + item.quantity, 0), "item", "itens")}</small></div><strong>${money(sale.total)}</strong></div>`).join("") : emptyState("▤", "Nenhuma venda", "Não há atendimentos neste período.");
}

function renderActivities() {
  $("#activityList").innerHTML = state.activities.length ? state.activities.slice(0, 8).map((activity) => `<div class="activity-item"><span class="activity-dot"></span><div><strong>${escapeHtml(activity.message)}</strong><small>${formatDate(activity.createdAt)}</small></div></div>`).join("") : emptyState("•", "Sem atividades", "As alterações da conta aparecerão aqui.");
}

function exportSales() {
  const sales = filteredSales();
  if (!sales.length) { toast("Não há vendas para exportar neste período.", "error"); return; }
  const rows = [["Data", "Venda", "Pagamento", "Produto", "Quantidade", "Preço unitário", "Total da venda"]];
  sales.forEach((sale) => sale.items.forEach((item) => rows.push([
    formatDate(sale.createdAt), sale.id, formatPayment(sale.paymentMethod), item.name, item.quantity,
    item.price.toFixed(2).replace(".", ","), sale.total.toFixed(2).replace(".", ","),
  ])));
  const csv = "\ufeff" + rows.map((row) => row.map(csvCell).join(";")).join("\r\n");
  const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = `vendas-${state.reportStart || "inicio"}-${state.reportEnd || "hoje"}.csv`;
  link.click();
  URL.revokeObjectURL(url);
  toast("Relatório exportado em CSV.");
}

function fillSettings() {
  const form = $("#businessForm");
  for (const [key, value] of Object.entries(state.settings)) {
    if (form.elements[key]) form.elements[key].value = value || "";
  }
}

async function saveSettings(event) {
  event.preventDefault();
  const button = $('button[type="submit"]', event.currentTarget);
  button.disabled = true;
  try {
    await api("/api/settings", { method: "PUT", data: Object.fromEntries(new FormData(event.currentTarget)) });
    await loadData();
    renderAll();
    toast("Configurações salvas.");
  } catch (error) { toast(error.message, "error"); }
  finally { button.disabled = false; }
}

async function changePassword(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const data = Object.fromEntries(new FormData(form));
  if (data.newPassword !== data.confirmPassword) { toast("A confirmação da nova senha não confere.", "error"); return; }
  const button = $('button[type="submit"]', form);
  button.disabled = true;
  try {
    await api("/api/account/password", { method: "PUT", data });
    form.reset();
    toast("Senha atualizada com sucesso.");
  } catch (error) { toast(error.message, "error"); }
  finally { button.disabled = false; }
}

function switchView(view) {
  const labels = {
    sale: ["OPERAÇÃO", "Frente de caixa"],
    inventory: ["CATÁLOGO", "Produtos e estoque"],
    reports: ["GESTÃO", "Relatórios"],
    settings: ["SISTEMA", "Configurações"],
  };
  if (!labels[view]) return;
  state.view = view;
  $$('[data-view]').forEach((button) => {
    const active = button.dataset.view === view;
    button.classList.toggle("active", active);
    if (active) button.setAttribute("aria-current", "page");
    else button.removeAttribute("aria-current");
  });
  $$('[data-view-panel]').forEach((panel) => panel.classList.toggle("active", panel.dataset.viewPanel === view));
  $("#viewEyebrow").textContent = labels[view][0];
  $("#viewTitle").textContent = labels[view][1];
  if (view === "reports") renderReports();
  closeSidebar();
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function openSidebar() {
  $("#sidebar").classList.add("open");
  $("#sidebarBackdrop").classList.add("open");
}

function closeSidebar() {
  $("#sidebar").classList.remove("open");
  $("#sidebarBackdrop").classList.remove("open");
}

function openModal(eyebrow, title, subtitle, content, wide = false) {
  const modal = $("#appModal");
  $("#modalEyebrow").textContent = eyebrow;
  $("#modalTitle").textContent = title;
  $("#modalSubtitle").textContent = subtitle;
  $("#modalBody").replaceChildren(content);
  modal.classList.toggle("wide", wide);
  if (!modal.open) modal.showModal();
  requestAnimationFrame(() => $("input[autofocus]", content)?.focus());
}

function closeModal() {
  const modal = $("#appModal");
  if (modal.open) modal.close();
}

async function api(path, options = {}) {
  const config = { method: options.method || "GET", headers: { Accept: "application/json" }, credentials: "same-origin" };
  if (options.data !== undefined) {
    config.headers["Content-Type"] = "application/json";
    config.body = JSON.stringify(options.data);
  }
  let response;
  try { response = await fetch(path, config); }
  catch (_) { throw Object.assign(new Error("Não foi possível conectar ao servidor."), { status: 0 }); }
  let payload = {};
  try { payload = await response.json(); } catch (_) { /* resposta sem JSON */ }
  if (!response.ok) {
    const error = Object.assign(new Error(payload.error || "Não foi possível concluir a operação."), { status: response.status });
    if (response.status === 401 && !path.startsWith("/api/auth/")) showAuth();
    throw error;
  }
  return payload;
}

function setCurrentDate() {
  const formatted = new Intl.DateTimeFormat("pt-BR", { weekday: "short", day: "2-digit", month: "short" }).format(new Date());
  $("#currentDate").textContent = formatted.replace(/^./, (letter) => letter.toUpperCase());
}

function setReportDefaults() {
  const end = new Date();
  const start = new Date();
  start.setDate(start.getDate() - 29);
  state.reportStart = toInputDate(start);
  state.reportEnd = toInputDate(end);
  $("#reportStart").value = state.reportStart;
  $("#reportEnd").value = state.reportEnd;
}

function setLoading(active) { $("#loadingOverlay").classList.toggle("active", active); }

function toast(message, type = "success") {
  const item = document.createElement("div");
  item.className = `toast ${type === "error" ? "error" : ""}`;
  item.textContent = `${type === "error" ? "!" : "✓"} ${message}`;
  $("#toastRegion").append(item);
  window.setTimeout(() => item.remove(), 4200);
}

function getProduct(id) { return state.products.find((product) => product.id === id); }
function money(value) { return moneyFormatter.format(Number(value) || 0); }
function formatDate(value) { try { return dateFormatter.format(new Date(value)); } catch (_) { return "—"; } }
function normalize(value) { return String(value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().trim(); }
function plural(value, singular, pluralText) { return `${value} ${value === 1 ? singular : pluralText}`; }
function toInputDate(date) { const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000); return local.toISOString().slice(0, 10); }
function formatPayment(method) { return ({ pix: "PIX", dinheiro: "Dinheiro", debito: "Cartão de débito", credito: "Cartão de crédito" })[method] || "Outro"; }
function csvCell(value) { return `"${String(value ?? "").replaceAll('"', '""')}"`; }

function stockStatus(product) {
  if (product.stock === 0) return { className: "out", label: "Sem estoque" };
  if (product.stock <= product.minStock) return { className: "low", label: `${product.stock} un. · Baixo` };
  return { className: "", label: `${product.stock} un.` };
}

function emptyState(icon, title, copy) {
  return `<div class="empty-state"><span class="empty-icon" aria-hidden="true">${icon}</span><strong>${escapeHtml(title)}</strong><p>${escapeHtml(copy)}</p></div>`;
}

function escapeHtml(value) {
  return String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#39;");
}

function buildPixPayload({ key, merchantName, city, amount }) {
  const cleanName = normalizePixField(merchantName || "MINHA BANCA", 25);
  const cleanCity = normalizePixField(city || "SAO PAULO", 15);
  const merchantAccount = tlv("00", "br.gov.bcb.pix") + tlv("01", key);
  const body = [tlv("00", "01"), tlv("26", merchantAccount), tlv("52", "0000"), tlv("53", "986"), tlv("54", Number(amount).toFixed(2)), tlv("58", "BR"), tlv("59", cleanName), tlv("60", cleanCity), tlv("62", tlv("05", "***"))].join("");
  return body + "6304" + crc16(body + "6304");
}

function normalizePixField(value, max) {
  return normalize(value).toUpperCase().replace(/[^A-Z0-9 .-]/g, "").slice(0, max).trim();
}

function tlv(id, value) {
  const text = String(value || "");
  const length = new TextEncoder().encode(text).length.toString().padStart(2, "0");
  return `${id}${length}${text}`;
}

function crc16(payload) {
  let crc = 0xffff;
  for (let index = 0; index < payload.length; index += 1) {
    crc ^= payload.charCodeAt(index) << 8;
    for (let bit = 0; bit < 8; bit += 1) crc = ((crc & 0x8000) ? (crc << 1) ^ 0x1021 : crc << 1) & 0xffff;
  }
  return crc.toString(16).toUpperCase().padStart(4, "0");
}

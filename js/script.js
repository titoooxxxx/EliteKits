// js/script.js — EliteKits
(() => {
  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => Array.from(document.querySelectorAll(sel));

  /* ── Prices ── */
  const PRICES = {
    fan:      25,
    pro:      30,
    long:     30,
    pro_long: 35,
    enfant:   25,
    retro:    30,
    flocage:  5,
    delivery: 5,
  };

  /* ── State ── */
  const state = {
    cart:        loadCart(),
    bannerShown: false,
    addPayload:  null,
  };

  /* ── Detect page category ── */
  function pageCategory() {
    const p = location.pathname.toLowerCase();
    if (p.endsWith('fan.html'))    return 'fan';
    if (p.endsWith('player.html')) return 'pro';
    if (p.endsWith('kids.html'))   return 'enfant';
    if (p.endsWith('retro.html'))  return 'retro';
    return null;
  }

  /* ════════════════════════════════════════
     METADATA + SEARCH
  ════════════════════════════════════════ */
  let metadata = {};
  let index    = [];

  fetch('metadata.json')
    .then((r) => { if (!r.ok) throw new Error('metadata.json not found'); return r.json(); })
    .then((data) => {
      metadata = data || {};
      buildIndex();
      initSearch();
      enhanceProductGrids();
    })
    .catch((err) => console.warn('Metadata load error:', err))
    .finally(() => {
      initCartUI();
    });

  function normalizeSrc(path) {
    if (!path) return '';
    if (path.startsWith('http') || path.startsWith('/')) return path;
    if (path.startsWith('images/')) return path;
    return `images/${path}`;
  }

  function tokenize(str) {
    return (str || '')
      .toString()
      .normalize('NFD')
      .replace(/\p{Diacritic}/gu, '')
      .toLowerCase()
      .split(/[^a-z0-9]+/)
      .filter(Boolean);
  }

  function buildIndex() {
    index = Object.entries(metadata).map(([path, info]) => {
      const src      = normalizeSrc(path);
      const team     = (info && (info.club || info.team)) || '';
      const category = (info && info.category) || guessCategoryFromPath(path);
      const player   = (info && info.player)   || guessPlayerFromPath(path);
      const title    = [team, player].filter(Boolean).join(' ') || 'Maillot';
      return {
        src, path, team, category, player, title,
        tokens: new Set([...tokenize(team), ...tokenize(category), ...tokenize(player)]),
      };
    });
  }

  function guessCategoryFromPath(p) {
    const m = String(p).toLowerCase().split('/')[0];
    if (m === 'player') return 'pro';
    if (m === 'kids')   return 'enfant';
    if (['fan', 'retro'].includes(m)) return m;
    return '';
  }

  function guessPlayerFromPath(p) {
    const name = String(p).toLowerCase();
    const players = ['messi','ronaldo','mbappe','neymar','haaland','vinicius',
                     'bellingham','griezmann','kane','salah'];
    return players.find((pl) => name.includes(pl)) || '';
  }

  function similarity(a, b) {
    const grams = (s) => {
      s = s.toLowerCase();
      const gs = new Set();
      for (let i = 0; i < s.length - 1; i++) gs.add(s.slice(i, i + 2));
      return gs;
    };
    const A = grams(a), B = grams(b);
    if (!A.size || !B.size) return 0;
    let inter = 0;
    A.forEach((g) => { if (B.has(g)) inter++; });
    return inter / (A.size + B.size - inter);
  }

  function rank(query) {
    const q      = query.trim();
    const qTok   = new Set(tokenize(q));
    const qLower = q.toLowerCase();
    return index
      .map((it) => {
        let score = 0;
        qTok.forEach((t) => {
          if (tokenize(it.team).includes(t))     score += 100;
          if (tokenize(it.player).includes(t))   score += 90;
          if (tokenize(it.category).includes(t)) score += 60;
        });
        if (it.team.toLowerCase().startsWith(qLower)) score += 80;
        else if (it.team.toLowerCase().includes(qLower)) score += 50;
        if (it.player && it.player.toLowerCase().includes(qLower)) score += 45;
        if (it.category && it.category.toLowerCase().includes(qLower)) score += 35;
        const bestField = [it.team, it.player].filter(Boolean)
          .sort((a, b) => similarity(b, q) - similarity(a, q))[0] || '';
        score += similarity(bestField, q) * 30;
        return { it, score };
      })
      .filter(({ score }) => score > 10)
      .sort((a, b) => b.score - a.score)
      .map(({ it }) => it);
  }

  function initSearch() {
    const input = $('#searchInput');
    if (!input) return;
    input.addEventListener('input', (e) => {
      const q = e.target.value.trim();
      const container = $('#resultsContainer');
      if (!container) return;
      if (!q) { container.innerHTML = ''; return; }
      renderResults(rank(q));
    });
  }

  /* ════════════════════════════════════════
     PRODUCT CARDS
  ════════════════════════════════════════ */
  function labelForCategory(cat) {
    const map = { fan:'Fan', pro:'Player', enfant:'Kids', retro:'Rétro', long:'Manches Longues' };
    return map[cat] || cat || 'Maillot';
  }

  function startingPrice(cat) {
    const map = { fan:25, pro:30, enfant:25, retro:30, long:30 };
    return (map[cat] || 25) + '€';
  }

  function createCard(item, withActions = true) {
    const card = document.createElement('div');
    card.className = 'product-card';
    card.innerHTML = `
      <div class="card-media">
        <img src="${item.src}" alt="${item.team || 'Maillot'}" loading="lazy" />
        <span class="badge">${labelForCategory(item.category)}</span>
      </div>
      <div class="card-info">
        <p class="team">${item.team || 'Maillot'}</p>
        ${item.player ? `<small class="muted">${item.player}</small>` : ''}
        <span class="price-tag">dès ${startingPrice(item.category)}</span>
        ${withActions
          ? `<button class="btn btn-primary btn-sm" style="width:100%"
               data-add
               data-src="${item.src}"
               data-team="${encodeURIComponent(item.team || '')}"
               data-category="${item.category || ''}">
               Ajouter au panier
             </button>`
          : ''}
      </div>`;
    return card;
  }

  function renderResults(list) {
    const container = $('#resultsContainer');
    if (!container) return;
    container.innerHTML = '';
    if (!list || !list.length) {
      container.innerHTML = '<p style="text-align:center;color:var(--muted);padding:2rem 0">Aucun maillot trouvé.</p>';
      return;
    }
    const frag = document.createDocumentFragment();
    list.slice(0, 60).forEach((it) => frag.appendChild(createCard(it)));
    container.appendChild(frag);
  }

  /* Enhance category pages: convert raw <img> list into product cards */
  function enhanceProductGrids() {
    const grid = $('.products');
    if (!grid) return;
    grid.className = 'product-grid';
    const cat = pageCategory();
    const items = $$('.products img, .product-grid img').map((img) => {
      const src  = img.getAttribute('src');
      const key  = src.startsWith('images/') ? src.replace(/^images\//, '') : src;
      const info = metadata[key] || {};
      return {
        src,
        team:     info.club || info.team || '',
        category: cat || info.category || guessCategoryFromPath(src),
        player:   info.player || guessPlayerFromPath(src),
      };
    });
    grid.innerHTML = '';
    const frag = document.createDocumentFragment();
    items.forEach((it) => frag.appendChild(createCard(it)));
    grid.appendChild(frag);
  }

  /* ════════════════════════════════════════
     CART — DATA
  ════════════════════════════════════════ */
  function loadCart() {
    try {
      const raw = localStorage.getItem('ek_cart');
      return raw ? JSON.parse(raw) : { items: [], ig: '', email: '' };
    } catch {
      return { items: [], ig: '', email: '' };
    }
  }

  function saveCart() {
    localStorage.setItem('ek_cart', JSON.stringify(state.cart));
    updateCartBadge();
    renderCartDrawer();
  }

  function addToCart(item) {
    state.cart.items.push(item);
    saveCart();
    openCart();
  }

  function priceForType(t) {
    return PRICES[t] ?? PRICES.fan;
  }

  function cartTotals() {
    const n = state.cart.items.length;
    let subtotal = 0;
    let flocageTotal = 0;
    state.cart.items.forEach((it) => {
      subtotal += priceForType(it.type);
      if (it.flocage) flocageTotal += PRICES.flocage;
    });
    const offerApplied = n >= 2;
    if (offerApplied) flocageTotal = 0;
    const delivery = n > 0 ? PRICES.delivery : 0;
    return { n, subtotal, flocageTotal, delivery, total: subtotal + flocageTotal + delivery, offerApplied };
  }

  /* ════════════════════════════════════════
     CART — UI INJECTION
  ════════════════════════════════════════ */
  function ensureUIRoots() {
    /* ── Cart Drawer ── */
    let drawer = $('#cartDrawer');
    if (!drawer) {
      drawer = document.createElement('div');
      drawer.id = 'cartDrawer';
      drawer.className = 'cart-drawer';
      document.body.appendChild(drawer);
    }
    if (!drawer.querySelector('.cart-panel')) {
      drawer.innerHTML = `
        <div class="cart-backdrop" id="cartBackdrop"></div>
        <div class="cart-panel">
          <div class="cart-header">
            <h3>Votre panier</h3>
            <button class="btn btn-text" id="closeCartBtn" aria-label="Fermer">✕</button>
          </div>
          <div class="cart-banner" id="igBanner">
            ⚠️ Pensez à nous suivre sur Instagram (@elitekits.jersey) avant de valider votre commande.
          </div>
          <div class="cart-promo">
            ⭐ Offre : flocage offert dès 2 maillots commandés !
          </div>
          <div class="cart-items" id="cartItems"></div>
          <div class="cart-summary" id="cartSummary"></div>
          <div class="cart-checkout">
            <div class="checkout-field">
              <label for="igInput">Pseudo Instagram (obligatoire)</label>
              <input id="igInput" type="text" placeholder="@votre_pseudo" autocomplete="off" />
            </div>
            <div class="checkout-field">
              <label for="emailInput">Email (confirmation de commande)</label>
              <input id="emailInput" type="email" placeholder="votre@email.com" autocomplete="email" />
            </div>
            <button class="btn btn-primary" id="checkoutBtn" style="width:100%">
              Valider la commande →
            </button>
          </div>
        </div>`;
    }

    /* ── Add-to-Cart Modal ── */
    let modal = $('#addModal');
    if (!modal) {
      modal = document.createElement('div');
      modal.id = 'addModal';
      modal.className = 'modal hidden';
      document.body.appendChild(modal);
    }
    if (!modal.querySelector('.modal-content')) {
      modal.innerHTML = `
        <div class="modal-content">
          <div class="modal-title">Ajouter au panier</div>
          <div class="modal-preview" id="modalPreview">
            <img id="previewImg" src="" alt="Aperçu maillot" />
            <div class="modal-preview-info">
              <h4 id="previewTeam">Maillot</h4>
              <p id="previewCat">Collection</p>
            </div>
          </div>
          <form id="addForm">
            <div class="form-group">
              <label for="typeSelect">Type de maillot</label>
              <select id="typeSelect" name="type">
                <option value="fan">Fan — 25€</option>
                <option value="pro">Player (Pro) — 30€</option>
                <option value="long">Manches longues — 30€</option>
                <option value="pro_long">Pro manches longues — 35€</option>
                <option value="enfant">Enfant — 25€</option>
                <option value="retro">Rétro — 30€</option>
              </select>
            </div>
            <div class="form-group">
              <label for="sizeSelect">Taille</label>
              <select id="sizeSelect" name="size">
                <option value="S">S</option>
                <option value="M" selected>M</option>
                <option value="L">L</option>
                <option value="XL">XL</option>
                <option value="XXL">XXL</option>
              </select>
            </div>
            <div class="form-group">
              <label class="checkbox-label">
                <input type="checkbox" id="flocCheck" />
                <span>Flocage personnalisé (+5€, offert dès 2 maillots)</span>
              </label>
              <div class="floc-fields hidden" id="flocFields">
                <input type="text" id="flocName"   placeholder="Nom au dos" />
                <input type="text" id="flocNumber" placeholder="Numéro" />
              </div>
            </div>
            <div class="modal-actions">
              <button type="button" class="btn btn-secondary" id="cancelAdd">Annuler</button>
              <button type="submit"  class="btn btn-primary">Ajouter</button>
            </div>
          </form>
        </div>`;
    }
  }

  /* ════════════════════════════════════════
     CART — INIT & EVENT BINDING
  ════════════════════════════════════════ */
  function initCartUI() {
    ensureUIRoots();

    /* Inject cart link if missing from nav */
    if (!$('[data-cart-open]')) {
      const nav = $('header nav ul');
      if (nav) {
        const li = document.createElement('li');
        li.className = 'cart-nav-item';
        li.innerHTML = `<a href="#" data-cart-open>🛒 Panier (<span id="cartCount">0</span>)</a>`;
        nav.appendChild(li);
      }
    }

    updateCartBadge();

    /* Global click delegation */
    document.body.addEventListener('click', (e) => {
      /* "Add to cart" button on product card */
      const addBtn = e.target.closest('[data-add]');
      if (addBtn) {
        e.preventDefault();
        openAddModal({
          src:      addBtn.dataset.src,
          team:     decodeURIComponent(addBtn.dataset.team || ''),
          category: addBtn.dataset.category || pageCategory() || 'fan',
        });
        return;
      }
      /* Open cart */
      if (e.target.closest('[data-cart-open]')) {
        e.preventDefault();
        openCart();
        return;
      }
      /* Close cart */
      if (e.target.id === 'closeCartBtn' || e.target.id === 'cartBackdrop') {
        closeCart();
        return;
      }
      /* Cancel modal */
      if (e.target.id === 'cancelAdd') { closeAddModal(); return; }
      /* Close modal clicking backdrop */
      if (e.target.id === 'addModal') { closeAddModal(); return; }
    });

    /* Flocage toggle */
    document.body.addEventListener('change', (e) => {
      if (e.target.id === 'flocCheck') {
        $('#flocFields')?.classList.toggle('hidden', !e.target.checked);
      }
    });

    /* Add form submit */
    document.body.addEventListener('submit', (e) => {
      if (e.target.id !== 'addForm') return;
      e.preventDefault();
      const payload  = state.addPayload || {};
      const type     = $('#typeSelect').value;
      const size     = $('#sizeSelect').value;
      const flocage  = $('#flocCheck').checked;
      const flocName = ($('#flocName')?.value || '').trim() || null;
      const flocNum  = ($('#flocNumber')?.value || '').trim() || null;
      addToCart({ ...payload, type, size, flocage, flocName, flocNumber: flocNum, unitPrice: priceForType(type) });
      closeAddModal();
    });

    /* Instagram + email inputs */
    document.body.addEventListener('input', (e) => {
      if (e.target.id === 'igInput')    { state.cart.ig    = e.target.value.trim(); saveCart(); }
      if (e.target.id === 'emailInput') { state.cart.email = e.target.value.trim(); saveCart(); }
    });

    /* Checkout button */
    document.body.addEventListener('click', (e) => {
      if (e.target.id === 'checkoutBtn') checkout();
    });

    renderCartDrawer();
  }

  /* ════════════════════════════════════════
     CART — RENDER
  ════════════════════════════════════════ */
  function updateCartBadge() {
    $$('#cartCount').forEach((el) => {
      el.textContent = String(state.cart.items.length);
    });
  }

  function renderCartDrawer() {
    const itemsEl = $('#cartItems');
    const sumEl   = $('#cartSummary');
    if (!itemsEl || !sumEl) return;

    /* Restore persisted values */
    const igInput    = $('#igInput');
    const emailInput = $('#emailInput');
    if (igInput    && !igInput.value)    igInput.value    = state.cart.ig    || '';
    if (emailInput && !emailInput.value) emailInput.value = state.cart.email || '';

    if (!state.cart.items.length) {
      itemsEl.innerHTML = '<p style="text-align:center;color:var(--muted);padding:2rem 0">Votre panier est vide.</p>';
      sumEl.innerHTML   = '';
      return;
    }

    itemsEl.innerHTML = '';
    state.cart.items.forEach((it, idx) => {
      const row = document.createElement('div');
      row.className = 'cart-item';
      row.innerHTML = `
        <img src="${it.src}" alt="${it.team || 'Maillot'}" />
        <div class="ci-main">
          <div class="ci-title">${it.team || 'Maillot'} <span class="badge">${it.type}</span> <span class="badge">${it.size}</span></div>
          ${it.flocage ? `<div class="ci-sub">Flocage: ${it.flocName || '—'} #${it.flocNumber || '—'}</div>` : ''}
          <div class="ci-price">${priceForType(it.type)}€${it.flocage ? ` + ${PRICES.flocage}€ flocage` : ''}</div>
        </div>
        <button class="btn btn-text" data-remove="${idx}" aria-label="Supprimer">✕</button>`;
      row.querySelector('[data-remove]').addEventListener('click', () => {
        state.cart.items.splice(idx, 1);
        saveCart();
      });
      itemsEl.appendChild(row);
    });

    const t = cartTotals();
    sumEl.innerHTML = `
      <div class="sum-row"><span>Sous-total</span><strong>${t.subtotal}€</strong></div>
      <div class="sum-row"><span>Flocage</span><strong>${t.flocageTotal}€${t.offerApplied ? ' <small style="color:var(--gold-light)">(offert ✓)</small>' : ''}</strong></div>
      <div class="sum-row"><span>Livraison</span><strong>${t.delivery}€</strong></div>
      <div class="sum-row total"><span>Total</span><strong>${t.total}€</strong></div>`;
  }

  /* ════════════════════════════════════════
     CART — OPEN / CLOSE
  ════════════════════════════════════════ */
  function openCart() {
    ensureUIRoots();
    const d = $('#cartDrawer');
    if (d) d.classList.add('open');
    if (!state.bannerShown) {
      const banner = $('#igBanner');
      if (banner) { banner.classList.add('visible'); state.bannerShown = true; }
    }
    renderCartDrawer();
  }

  function closeCart() {
    $('#cartDrawer')?.classList.remove('open');
  }

  /* ════════════════════════════════════════
     MODAL — OPEN / CLOSE
  ════════════════════════════════════════ */
  function openAddModal(payload) {
    ensureUIRoots();
    state.addPayload = payload;
    const modal = $('#addModal');
    const form  = $('#addForm');
    if (!modal || !form) return;

    form.reset();
    $('#flocFields')?.classList.add('hidden');

    /* Set default type based on category */
    const typeMap = { fan:'fan', pro:'pro', enfant:'enfant', retro:'retro' };
    const defType = typeMap[payload.category] || 'fan';
    const typeEl  = $('#typeSelect');
    if (typeEl) typeEl.value = defType;

    /* Fill preview */
    const previewImg  = $('#previewImg');
    const previewTeam = $('#previewTeam');
    const previewCat  = $('#previewCat');
    if (previewImg)  previewImg.src         = payload.src || '';
    if (previewImg)  previewImg.alt         = payload.team || 'Maillot';
    if (previewTeam) previewTeam.textContent = payload.team || 'Maillot';
    if (previewCat)  previewCat.textContent  = labelForCategory(payload.category);

    modal.classList.remove('hidden');
  }

  function closeAddModal() {
    $('#addModal')?.classList.add('hidden');
    state.addPayload = null;
  }

  /* ════════════════════════════════════════
     CHECKOUT
  ════════════════════════════════════════ */
  async function checkout() {
    const ig       = ($('#igInput')?.value    || state.cart.ig    || '').trim();
    const email    = ($('#emailInput')?.value || state.cart.email || '').trim();

    if (!ig) {
      alert('Merci de renseigner votre pseudo Instagram avant de valider.');
      return;
    }
    if (!state.cart.items.length) {
      alert('Votre panier est vide.');
      return;
    }

    const totals = cartTotals();
    const order  = {
      instagram:     ig,
      customerEmail: email || null,
      totals,
      items: state.cart.items,
    };

    const API_BASE = (window.ELITEKITS_API || '').replace(/\/$/, '');
    const isLocal  = /localhost|127\./.test(location.hostname);
    const endpoint = API_BASE ? `${API_BASE}/api/order` : '/api/order';

    /* In production without a configured API → mailto fallback immediately */
    if (!isLocal && !API_BASE) {
      mailtoFallback(order);
      return;
    }

    try {
      const res = await fetch(endpoint, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify(order),
        mode:    API_BASE ? 'cors' : 'same-origin',
      });
      if (!res.ok) throw new Error('server error');
      const confirmMsg = email
        ? `Commande envoyée ! Un email de confirmation a été envoyé à ${email}.`
        : 'Commande envoyée au vendeur. Merci !';
      alert(confirmMsg);
      resetCart(ig, email);
    } catch {
      mailtoFallback(order);
    }
  }

  function mailtoFallback(order) {
    const subject = encodeURIComponent('Nouvelle commande EliteKits');
    const body    = encodeURIComponent(formatOrderText(order));
    window.location.href = `mailto:cornictitouan@yahoo.com?subject=${subject}&body=${body}`;
    resetCart(order.instagram, order.customerEmail || '');
  }

  function resetCart(ig, email) {
    state.cart = { items: [], ig, email };
    saveCart();
    closeCart();
  }

  function formatOrderText(order) {
    const lines = [`Instagram : ${order.instagram}`];
    if (order.customerEmail) lines.push(`Email client : ${order.customerEmail}`);
    lines.push('');
    order.items.forEach((it, i) => {
      lines.push(`#${i + 1}  ${it.team || 'Maillot'} | ${it.type} | Taille ${it.size}`);
      if (it.flocage) lines.push(`       Flocage : ${it.flocName || '—'} #${it.flocNumber || '—'}`);
      lines.push(`       Photo : ${location.origin}/${it.src}`);
    });
    lines.push('');
    lines.push(`Sous-total : ${order.totals.subtotal}€`);
    lines.push(`Flocage    : ${order.totals.flocageTotal}€${order.totals.offerApplied ? ' (offert)' : ''}`);
    lines.push(`Livraison  : ${order.totals.delivery}€`);
    lines.push(`TOTAL      : ${order.totals.total}€`);
    return lines.join('\n');
  }

  /* Boot */
  initCartUI();
})();

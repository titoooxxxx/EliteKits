// js/script.js

(() => {
  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => Array.from(document.querySelectorAll(sel));

  const searchInput = document.getElementById('searchInput');
  const resultsContainer = document.getElementById('resultsContainer');

  let metadata = {};
  let index = [];

  const PRICES = {
    fan: 25,
    pro: 30,
    long: 30,
    pro_long: 35,
    enfant: 25,
    retro: 30,
    flocage: 5,
    delivery: 5
  };

  const state = {
    cart: loadCart(),
    bannerShown: false
  };

  function pageCategory() {
    const p = location.pathname.toLowerCase();
    if (p.endsWith('fan.html')) return 'fan';
    if (p.endsWith('player.html')) return 'pro';
    if (p.endsWith('kids.html')) return 'enfant';
    if (p.endsWith('retro.html')) return 'retro';
    return null;
  }

  // Load metadata
  fetch('metadata.json')
    .then((res) => {
      if (!res.ok) throw new Error('metadata.json introuvable');
      return res.json();
    })
    .then((data) => {
      metadata = data || {};
      buildIndex();
      initSearch();
      enhanceProductGrids();
      initCartUI();
    })
    .catch((err) => console.error('Erreur chargement metadata:', err));

  function normalizeSrc(path) {
    if (!path) return '';
    if (path.startsWith('http://') || path.startsWith('https://') || path.startsWith('/')) return path;
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
      const src = normalizeSrc(path);
      const team = (info && (info.club || info.team)) || '';
      const category = (info && info.category) || guessCategoryFromPath(path);
      const player = (info && info.player) || guessPlayerFromPath(path);
      const title = [team, player].filter(Boolean).join(' ') || 'Maillot';
      return { src, path, team, category, player, title, tokens: new Set([...tokenize(team), ...tokenize(category), ...tokenize(player)]) };
    });
  }

  function guessCategoryFromPath(p) {
    const m = String(p).toLowerCase().split('/')[0];
    if (['fan', 'player', 'kids', 'retro'].includes(m)) {
      if (m === 'player') return 'pro';
      if (m === 'kids') return 'enfant';
      return m; // fan, retro
    }
    return '';
  }

  function guessPlayerFromPath(p) {
    const name = String(p).toLowerCase();
    const players = ['messi', 'ronaldo', 'mbappe', 'neymar', 'haaland', 'vinicius', 'bellingham', 'griezmann', 'kane', 'salah'];
    const hit = players.find((pl) => name.includes(pl));
    return hit ? hit : '';
  }

  function similarity(a, b) {
    // Jaccard over bigrams
    const grams = (s) => {
      s = s.toLowerCase();
      const gs = new Set();
      for (let i = 0; i < s.length - 1; i++) gs.add(s.slice(i, i + 2));
      return gs;
    };
    const A = grams(a), B = grams(b);
    if (A.size === 0 || B.size === 0) return 0;
    let inter = 0;
    A.forEach((g) => {
      if (B.has(g)) inter++;
    });
    return inter / (A.size + B.size - inter);
  }

  function rank(query) {
    const q = query.trim();
    const qTok = new Set(tokenize(q));
    const qLower = q.toLowerCase();
    return index
      .map((it) => {
        let score = 0;
        // exact token hits on team/player
        qTok.forEach((t) => {
          if (tokenize(it.team).includes(t)) score += 100;
          if (tokenize(it.player).includes(t)) score += 90;
          if (tokenize(it.category).includes(t)) score += 60;
        });
        // substring boosts
        if (it.team.toLowerCase().startsWith(qLower)) score += 80;
        else if (it.team.toLowerCase().includes(qLower)) score += 50;
        if (it.player && it.player.toLowerCase().includes(qLower)) score += 45;
        if (it.category && it.category.toLowerCase().includes(qLower)) score += 35;
        // fuzzy fallback
        const bestField = [it.team, it.player].filter(Boolean).sort((a, b) => similarity(b, q) - similarity(a, q))[0] || '';
        score += similarity(bestField, q) * 30;
        return { it, score };
      })
      .filter(({ score }) => score > 10)
      .sort((a, b) => b.score - a.score)
      .map(({ it }) => it);
  }

  function createCard(item, withActions = true) {
    const card = document.createElement('div');
    card.className = 'product-card';
    card.innerHTML = `
      <div class="card-media">
        <img src="${item.src}" alt="${item.team || 'Maillot'}" loading="lazy">
        <span class="badge">${(item.category || 'maillot').toUpperCase()}</span>
      </div>
      <div class="card-info">
        <p class="team">${item.team || 'Inconnu'}</p>
        ${item.player ? `<small class="muted">${item.player}</small>` : ''}
        ${withActions ? `<button class="btn btn-primary" data-add data-src="${item.src}" data-team="${encodeURIComponent(item.team || '')}" data-category="${item.category || ''}">Ajouter au panier</button>` : ''}
      </div>
    `;
    return card;
  }

  function renderResults(list) {
    if (!resultsContainer) return;
    resultsContainer.innerHTML = '';
    if (!list || list.length === 0) {
      resultsContainer.innerHTML = '<p>Aucun maillot trouvé.</p>';
      return;
    }
    const frag = document.createDocumentFragment();
    list.slice(0, 60).forEach((it) => frag.appendChild(createCard(it)));
    resultsContainer.appendChild(frag);
  }

  function initSearch() {
    if (!searchInput) return;
    searchInput.addEventListener('input', (e) => {
      const q = e.target.value || '';
      if (!q.trim()) {
        resultsContainer.innerHTML = '';
        return;
      }
      renderResults(rank(q));
    });
  }

  // Enhance category pages by turning <img> lists into product cards
  function enhanceProductGrids() {
    const grid = $('.products');
    if (!grid) return;
    grid.classList.add('product-grid');
    const cat = pageCategory();
    const items = $$('.products img').map((img) => {
      const src = img.getAttribute('src');
      const key = src.startsWith('images/') ? src.replace(/^images\//, '') : src;
      const info = metadata[key] || {};
      const team = (info.club || info.team || '');
      const category = cat || info.category || guessCategoryFromPath(src);
      const player = info.player || guessPlayerFromPath(src);
      return { src, team, category, player };
    });
    grid.innerHTML = '';
    const frag = document.createDocumentFragment();
    items.forEach((it) => frag.appendChild(createCard(it)));
    grid.appendChild(frag);
  }

  // CART
  function loadCart() {
    try {
      const raw = localStorage.getItem('ek_cart');
      return raw ? JSON.parse(raw) : { items: [], ig: '' };
    } catch {
      return { items: [], ig: '' };
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
  function cartTotals() {
    const n = state.cart.items.length;
    let subtotal = 0;
    let flocageTotal = 0;
    state.cart.items.forEach((it) => {
      const base = priceForType(it.type);
      subtotal += base;
      if (it.flocage) flocageTotal += PRICES.flocage;
    });
    // Offer: flocage free if 2+ jerseys
    if (n >= 2) flocageTotal = 0;
    const delivery = n > 0 ? PRICES.delivery : 0;
    const total = subtotal + flocageTotal + delivery;
    return { n, subtotal, flocageTotal, delivery, total, offerApplied: n >= 2 };
  }
  function priceForType(t) {
    switch (t) {
      case 'fan': return PRICES.fan;
      case 'pro': return PRICES.pro;
      case 'long': return PRICES.long;
      case 'pro_long': return PRICES.pro_long;
      case 'enfant': return PRICES.enfant;
      case 'retro': return PRICES.retro;
      default: return PRICES.fan;
    }
  }

  // UI creation (modal + drawer) injected once
  function ensureUIRoots() {
    const drawer = $('#cartDrawer');
    const drawerMarkup = `
        <div class="cart-panel">
          <div class="cart-header">
            <h3>Votre panier</h3>
            <button class="btn btn-text" id="closeCartBtn">✕</button>
          </div>
          <div class=\"cart-banner\" style=\"display:none\" id=\"igBanner\">⚠️ Pensez à m’ajouter sur Instagram (@elitekits.jersey) avant de valider votre commande. Sinon, elle ne sera pas prise en compte.</div>
          <div class="cart-items" id="cartItems"></div>
          <div class="cart-summary" id="cartSummary"></div>
          <div class="cart-checkout">
            <label for="igInput">Votre pseudo Instagram (obligatoire)</label>
            <input id="igInput" type="text" placeholder="@elitekits.jersey" />
            <button class="btn btn-primary" id="checkoutBtn">Valider la commande</button>
          </div>
        </div>`;
    if (!drawer) {
      const d = document.createElement('div');
      d.id = 'cartDrawer';
      d.className = 'cart-drawer';
      d.innerHTML = drawerMarkup;
      document.body.appendChild(d);
    } else if (!drawer.querySelector('.cart-panel')) {
      drawer.classList.add('cart-drawer');
      drawer.innerHTML = drawerMarkup;
      drawer.style.display = '';
    }

    const modal = $('#addModal');
    const modalMarkup = `
        <div class="modal-content">
          <h3>Ajouter au panier</h3>
          <form id="addForm">
            <div class="row">
              <label>Type</label>
              <select name="type" id="typeSelect">
                <option value="fan">Fan - 25€</option>
                <option value="pro">Pro - 30€</option>
                <option value="long">Manches longues - 30€</option>
                <option value="pro_long">Pro manches longues - 35€</option>
                <option value="enfant">Enfant - 25€</option>
                <option value="retro">Rétro - 30€</option>
              </select>
            </div>
            <div class="row">
              <label>Taille</label>
              <select name="size" id="sizeSelect">
                <option value="S">S</option>
                <option value="M" selected>M</option>
                <option value="L">L</option>
                <option value="XL">XL</option>
              </select>
            </div>
            <div class="row">
              <label><input type="checkbox" id="flocCheck"/> Flocage (+5€)</label>
            </div>
            <div id="flocFields" class="row hidden">
              <input type="text" id="flocName" placeholder="Nom au dos" />
              <input type="text" id="flocNumber" placeholder="Numéro" />
            </div>
            <div class="actions">
              <button type="button" class="btn" id="cancelAdd">Annuler</button>
              <button type="submit" class="btn btn-primary">Ajouter</button>
            </div>
          </form>
        </div>`;
    if (!modal) {
      const m = document.createElement('div');
      m.id = 'addModal';
      m.className = 'modal hidden';
      m.innerHTML = modalMarkup;
      document.body.appendChild(m);
    } else if (!modal.querySelector('.modal-content')) {
      modal.classList.add('modal', 'hidden');
      modal.innerHTML = modalMarkup;
      modal.style.display = '';
    }
  }

  function initCartUI() {
    ensureUIRoots();
    // Header cart badge
    if (!$('[data-cart-open]')) {
      // try to add a link into nav
      const nav = document.querySelector('header nav ul');
      if (nav) {
        const li = document.createElement('li');
        li.innerHTML = `<a href="#" data-cart-open>Panier (<span id="cartCount">0</span>)</a>`;
        nav.appendChild(li);
      }
    }
    updateCartBadge();

    document.body.addEventListener('click', (e) => {
      const addBtn = e.target.closest('[data-add]');
      if (addBtn) {
        const src = addBtn.getAttribute('data-src');
        const team = decodeURIComponent(addBtn.getAttribute('data-team') || '');
        const cat = addBtn.getAttribute('data-category') || pageCategory() || 'fan';
        openAddModal({ src, team, category: cat });
        e.preventDefault();
        return;
      }
      if (e.target.matches('[data-cart-open]')) {
        openCart();
        e.preventDefault();
        return;
      }
      if (e.target.id === 'closeCartBtn') closeCart();
      if (e.target.id === 'cancelAdd') closeAddModal();
    });

    // Modal interactivity
    const flocCheck = document.getElementById('flocCheck');
    const flocFields = document.getElementById('flocFields');
    if (flocCheck) flocCheck.addEventListener('change', () => flocFields.classList.toggle('hidden', !flocCheck.checked));

    const addForm = document.getElementById('addForm');
    if (addForm) addForm.addEventListener('submit', (e) => {
      e.preventDefault();
      const payload = addForm.dataset.payload ? JSON.parse(addForm.dataset.payload) : {};
      const type = document.getElementById('typeSelect').value;
      const size = document.getElementById('sizeSelect').value;
      const flocage = document.getElementById('flocCheck').checked;
      const name = document.getElementById('flocName').value.trim();
      const number = document.getElementById('flocNumber').value.trim();
      addToCart({ ...payload, type, size, flocage, flocName: name || null, flocNumber: number || null, unitPrice: priceForType(type) });
      closeAddModal();
    });

    const checkoutBtn = document.getElementById('checkoutBtn');
    if (checkoutBtn) checkoutBtn.addEventListener('click', checkout);

    const igInput = document.getElementById('igInput');
    if (igInput) {
      igInput.value = state.cart.ig || '';
      igInput.addEventListener('input', () => {
        state.cart.ig = igInput.value.trim();
        saveCart();
      });
    }

    renderCartDrawer();
  }

  function updateCartBadge() {
    const countEl = document.getElementById('cartCount');
    if (countEl) countEl.textContent = String(state.cart.items.length);
  }

  function renderCartDrawer() {
    const itemsEl = document.getElementById('cartItems');
    const sumEl = document.getElementById('cartSummary');
    if (!itemsEl || !sumEl) return;
    if (state.cart.items.length === 0) {
      itemsEl.innerHTML = '<p>Votre panier est vide.</p>';
      sumEl.innerHTML = '';
      return;
    }
    itemsEl.innerHTML = '';
    state.cart.items.forEach((it, idx) => {
      const row = document.createElement('div');
      row.className = 'cart-item';
      row.innerHTML = `
        <img src="${it.src}" alt="${it.team || 'Maillot'}"/>
        <div class="ci-main">
          <div class="ci-title">${it.team || 'Maillot'} <span class="badge">${it.type}</span> <span class="badge">${it.size}</span></div>
          ${it.flocage ? `<div class="muted">Flocage: ${it.flocName || '-'} #${it.flocNumber || '-'}</div>` : ''}
          <div class="ci-price">${priceForType(it.type)}€${it.flocage ? ` + ${PRICES.flocage}€ flocage` : ''}</div>
        </div>
        <button class="btn btn-text" data-remove="${idx}">Supprimer</button>
      `;
      row.querySelector('[data-remove]')?.addEventListener('click', () => {
        state.cart.items.splice(idx, 1);
        saveCart();
      });
      itemsEl.appendChild(row);
    });
    const t = cartTotals();
    sumEl.innerHTML = `
      <div class="sum-row"><span>Sous-total</span><strong>${t.subtotal}€</strong></div>
      <div class="sum-row"><span>Flocage</span><strong>${t.flocageTotal}€${t.offerApplied ? ' (offert dès 2 maillots)' : ''}</strong></div>
      <div class="sum-row"><span>Livraison</span><strong>${t.delivery}€</strong></div>
      <div class="sum-row total"><span>Total</span><strong>${t.total}€</strong></div>
    `;
  }

  function openCart() {
    ensureUIRoots();
    const d = $('#cartDrawer');
    if (d) {
      d.style.display = '';
      d.classList.add('open');
    }
    const banner = $('#igBanner');
    if (banner && !state.bannerShown) {
      banner.style.display = 'block';
      state.bannerShown = true;
    }
  }
  function closeCart() { $('#cartDrawer')?.classList.remove('open'); }

  function openAddModal(payload) {
    ensureUIRoots();
    const modal = $('#addModal');
    const form = $('#addForm');
    if (!modal || !form) return;
    const def = payload.category || 'fan';
    form.reset();
    document.getElementById('typeSelect').value = def;
    document.getElementById('flocFields').classList.add('hidden');
    form.dataset.payload = JSON.stringify(payload);
    modal.classList.remove('hidden');
  }
  function closeAddModal() { $('#addModal')?.classList.add('hidden'); }

  async function checkout() {
    const ig = (document.getElementById('igInput')?.value || '').trim();
    if (!ig) {
      alert('Merci de renseigner votre pseudo Instagram.');
      return;
    }
    const totals = cartTotals();
    const order = { instagram: ig, totals, items: state.cart.items };
    try {
      const res = await fetch('/api/order', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(order) });
      if (!res.ok) throw new Error('Serveur indisponible');
      alert('Commande envoyée au vendeur. Merci !');
      state.cart = { items: [], ig };
      saveCart();
      closeCart();
    } catch (e) {
      // fallback: open mailto with summary
      const subject = encodeURIComponent('Nouvelle commande EliteKits');
      const body = encodeURIComponent(formatOrderText(order));
      window.location.href = `mailto:cornictitouan@yahoo.com?subject=${subject}&body=${body}`;
    }
  }

  function formatOrderText(order) {
    const lines = [];
    lines.push(`Instagram: ${order.instagram}`);
    lines.push('');
    order.items.forEach((it, i) => {
      lines.push(`#${i + 1} ${it.team || 'Maillot'} | ${it.type} | ${it.size}`);
      if (it.flocage) lines.push(`  Flocage: ${it.flocName || '-'} #${it.flocNumber || '-'}`);
      lines.push(`  Photo: ${location.origin}/${it.src}`);
    });
    lines.push('');
    lines.push(`Sous-total: ${order.totals.subtotal}€`);
    lines.push(`Flocage: ${order.totals.flocageTotal}€${order.totals.offerApplied ? ' (offert)' : ''}`);
    lines.push(`Livraison: ${order.totals.delivery}€`);
    lines.push(`TOTAL: ${order.totals.total}€`);
    return lines.join('\n');
  }

})();

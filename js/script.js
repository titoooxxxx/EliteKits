// js/script.js — EliteKits v2.0 (Premium Design)
(() => {
  const $ = (sel, ctx = document) => ctx.querySelector(sel);
  const $$ = (sel, ctx = document) => Array.from(ctx.querySelectorAll(sel));

  /* ─────────────────────────────────────────
     PRICES
  ───────────────────────────────────────── */
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

  /* ─────────────────────────────────────────
     STATE
  ───────────────────────────────────────── */
  const state = {
    cart:       loadCart(),
    addPayload: null,
    modalType:  'fan',
    modalSize:  'M',
    activeFilter: 'all',
    allResults: [],
  };

  /* ─────────────────────────────────────────
     DETECT PAGE CATEGORY
  ───────────────────────────────────────── */
  function pageCategory() {
    const p = location.pathname.toLowerCase();
    if (p.includes('fan.html'))    return 'fan';
    if (p.includes('player.html')) return 'pro';
    if (p.includes('kids.html'))   return 'enfant';
    if (p.includes('retro.html'))  return 'retro';
    return null;
  }

  /* ─────────────────────────────────────────
     METADATA + SEARCH ENGINE
  ───────────────────────────────────────── */
  let metadata = {};
  let searchIndex = [];

  fetch('metadata.json')
    .then(r => { if (!r.ok) throw new Error(); return r.json(); })
    .then(data => {
      metadata = data || {};
      buildIndex();
      initSearch();
      enhanceProductGrids();
    })
    .catch(() => {
      enhanceProductGrids();
    })
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
    searchIndex = Object.entries(metadata).map(([path, info]) => {
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
    return players.find(pl => name.includes(pl)) || '';
  }

  function similarity(a, b) {
    const grams = s => {
      s = s.toLowerCase();
      const gs = new Set();
      for (let i = 0; i < s.length - 1; i++) gs.add(s.slice(i, i + 2));
      return gs;
    };
    const A = grams(a), B = grams(b);
    if (!A.size || !B.size) return 0;
    let inter = 0;
    A.forEach(g => { if (B.has(g)) inter++; });
    return inter / (A.size + B.size - inter);
  }

  function rank(query) {
    const q      = query.trim();
    const qTok   = new Set(tokenize(q));
    const qLower = q.toLowerCase();
    return searchIndex
      .map(it => {
        let score = 0;
        qTok.forEach(t => {
          if (tokenize(it.team).includes(t))     score += 100;
          if (tokenize(it.player).includes(t))   score += 90;
          if (tokenize(it.category).includes(t)) score += 60;
        });
        if (it.team.toLowerCase().startsWith(qLower))    score += 80;
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

  /* ─────────────────────────────────────────
     SEARCH UI
  ───────────────────────────────────────── */
  function initSearch() {
    const input   = $('#searchInput');
    const clearBtn = $('#searchClear');
    if (!input) return;

    input.addEventListener('input', e => {
      const q = e.target.value.trim();
      if (clearBtn) clearBtn.classList.toggle('visible', q.length > 0);
      if (!q) { hideResults(); return; }
      const results = rank(q);
      state.allResults = results;
      applyFilterAndRender();
    });

    // Clear button
    clearBtn?.addEventListener('click', () => {
      input.value = '';
      clearBtn.classList.remove('visible');
      hideResults();
    });

    // Filter chips
    $$('.filter-chip').forEach(chip => {
      chip.addEventListener('click', () => {
        $$('.filter-chip').forEach(c => c.classList.remove('active'));
        chip.classList.add('active');
        state.activeFilter = chip.dataset.filter || 'all';
        applyFilterAndRender();
      });
    });
  }

  function applyFilterAndRender() {
    const filter = state.activeFilter;
    let list = state.allResults;

    if (filter !== 'all') {
      // Map filter chip value to category values
      const filterMap = { fan: 'fan', player: 'pro', retro: 'retro', kids: 'enfant' };
      const cat = filterMap[filter] || filter;
      list = list.filter(it => it.category === cat || it.category === filter);
    }

    renderResults(list);
  }

  function renderResults(list) {
    const wrap = $('#searchResultsWrap');
    const container = $('#searchResults');
    const countEl = $('#resultsCount');
    if (!container || !wrap) return;

    if (!list || !list.length) {
      container.innerHTML = '<p style="text-align:center;color:var(--text-3);padding:3rem 0;grid-column:1/-1">Aucun maillot trouv\u00e9 pour cette recherche.</p>';
      if (countEl) countEl.innerHTML = 'Aucun r\u00e9sultat';
      wrap.style.display = 'block';
      return;
    }

    const shown = list.slice(0, 60);
    if (countEl) countEl.innerHTML = `<strong>${shown.length}</strong> r\u00e9sultats${list.length > 60 ? ` sur ${list.length}` : ''}`;

    const frag = document.createDocumentFragment();
    shown.forEach(it => frag.appendChild(createCard(it)));
    container.innerHTML = '';
    container.appendChild(frag);
    wrap.style.display = 'block';
  }

  function hideResults() {
    const wrap = $('#searchResultsWrap');
    if (wrap) wrap.style.display = 'none';
    state.allResults = [];
  }

  /* ─────────────────────────────────────────
     PRODUCT CARDS
  ───────────────────────────────────────── */
  function categoryLabel(cat) {
    const map = { fan: 'Fan', pro: 'Player', enfant: 'Kids', retro: 'R\u00e9tro', long: 'ML' };
    return map[cat] || cat || 'Maillot';
  }

  function categoryBadgeClass(cat) {
    const map = { fan: 'badge-fan', pro: 'badge-player', enfant: 'badge-kids', retro: 'badge-retro', long: 'badge-player' };
    return map[cat] || 'badge-fan';
  }

  function startingPrice(cat) {
    const map = { fan: 25, pro: 30, enfant: 25, retro: 30, long: 30 };
    return (map[cat] || 25) + '\u20ac';
  }

  function createCard(item) {
    const card = document.createElement('div');
    card.className = 'product-card';

    const addDataStr = JSON.stringify({
      src:      item.src,
      team:     item.team || '',
      category: item.category || 'fan',
    }).replace(/"/g, '&quot;');

    card.innerHTML = `
      <div class="product-card-img">
        <img src="${item.src}" alt="${item.team || 'Maillot'}" loading="lazy">
        <span class="product-badge ${categoryBadgeClass(item.category)}">${categoryLabel(item.category)}</span>
        <button class="product-card-add" data-add="${addDataStr}" aria-label="Ajouter au panier">
          <i class="fa-solid fa-plus"></i>
        </button>
      </div>
      <div class="product-card-info">
        <div class="product-team">${item.team || 'Maillot'}</div>
        ${item.player ? `<div class="product-player">${item.player}</div>` : ''}
        <div class="product-price"><span class="from">d\u00e8s</span> ${startingPrice(item.category)}</div>
      </div>`;
    return card;
  }

  /* Enhance category pages: convert raw <img> tags into product cards */
  function enhanceProductGrids() {
    const grid = $('#products') || $('.products');
    if (!grid) return;

    const cat = pageCategory();
    const imgs = $$('img', grid);
    if (!imgs.length) return;

    const items = imgs.map(img => {
      const src  = img.getAttribute('src');
      const key  = src && src.startsWith('images/') ? src.replace(/^images\//, '') : src;
      const info = (key && metadata[key]) || {};
      return {
        src,
        team:     info.club || info.team || '',
        category: cat || info.category || guessCategoryFromPath(src || ''),
        player:   info.player || guessPlayerFromPath(src || ''),
      };
    });

    // Replace all raw imgs with product cards
    grid.innerHTML = '';
    const frag = document.createDocumentFragment();
    items.forEach(it => frag.appendChild(createCard(it)));
    grid.appendChild(frag);
  }

  /* ─────────────────────────────────────────
     CART — DATA LAYER
  ───────────────────────────────────────── */
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
    showToast(`${item.team || 'Maillot'} ajout\u00e9 au panier`);
  }

  function priceForType(t) { return PRICES[t] ?? PRICES.fan; }

  function cartTotals() {
    const n = state.cart.items.length;
    let subtotal = 0, flocageTotal = 0;
    state.cart.items.forEach(it => {
      subtotal += priceForType(it.type);
      if (it.flocage) flocageTotal += PRICES.flocage;
    });
    const offerApplied = n >= 2;
    if (offerApplied) flocageTotal = 0;
    const delivery = n > 0 ? PRICES.delivery : 0;
    return { n, subtotal, flocageTotal, delivery, total: subtotal + flocageTotal + delivery, offerApplied };
  }

  /* ─────────────────────────────────────────
     TOAST NOTIFICATION
  ───────────────────────────────────────── */
  function showToast(msg) {
    const toast = $('#toast');
    const msgEl = $('#toastMsg');
    if (!toast) return;
    if (msgEl) msgEl.textContent = msg;
    toast.classList.add('show');
    setTimeout(() => toast.classList.remove('show'), 2800);
  }

  /* ─────────────────────────────────────────
     CART BADGE
  ───────────────────────────────────────── */
  function updateCartBadge() {
    const n = state.cart.items.length;
    $$('#cartCount').forEach(el => {
      el.textContent = String(n);
      el.classList.toggle('visible', n > 0);
      // Bounce animation
      if (n > 0) {
        el.classList.remove('bounce');
        void el.offsetWidth; // reflow
        el.classList.add('bounce');
      }
    });
  }

  /* ─────────────────────────────────────────
     CART — UI INJECTION
  ───────────────────────────────────────── */
  function ensureCartDrawer() {
    const drawer = $('#cartDrawer');
    if (!drawer || drawer.querySelector('.cart-head')) return;

    drawer.innerHTML = `
      <div class="cart-head">
        <div class="cart-head-title">
          <i class="fa-solid fa-bag-shopping"></i>
          Panier
          <span class="cart-head-n" id="cartItemCount">0</span>
        </div>
        <button class="cart-close-btn" id="cartCloseBtn" aria-label="Fermer">
          <i class="fa-solid fa-xmark"></i>
        </button>
      </div>
      <div class="cart-promo">
        <i class="fa-solid fa-tag"></i>
        Flocage offert d\u00e8s 2 maillots command\u00e9s&nbsp;!
      </div>
      <div class="cart-items-scroll" id="cartItemsScroll"></div>
      <div class="cart-foot">
        <div class="cart-summary-box" id="cartSummaryBox"></div>
        <div class="cart-form-fields">
          <input type="text"  class="cart-field" id="igInput"    placeholder="@votre_pseudo_instagram" autocomplete="off">
          <input type="email" class="cart-field" id="emailInput" placeholder="Email (confirmation optionnel)" autocomplete="email">
        </div>
        <label class="cart-ig-confirm">
          <input type="checkbox" id="igFollowCheck">
          Je confirme suivre <strong>@elitekits.jersey</strong> sur Instagram
        </label>
        <button class="cart-checkout-btn" id="checkoutBtn">
          <i class="fa-solid fa-paper-plane"></i>
          Valider ma commande
        </button>
      </div>`;
  }

  function ensureModal() {
    const modalBox = $('#modalBox');
    if (!modalBox || modalBox.querySelector('.modal-img-area')) return;

    modalBox.innerHTML = `
      <div class="modal-img-area">
        <img id="modalImg" src="" alt="Aper\u00e7u maillot">
        <button class="modal-img-close" id="modalImgClose" aria-label="Fermer">
          <i class="fa-solid fa-xmark"></i>
        </button>
      </div>
      <div class="modal-body-pad">
        <div class="modal-team-name" id="modalTeamName">Maillot</div>

        <div class="modal-opt-group">
          <span class="modal-opt-label">Type de maillot</span>
          <div class="modal-pills" id="typePills">
            <button class="modal-pill active" data-type="fan"      data-price="25">Fan — 25€</button>
            <button class="modal-pill"        data-type="pro"      data-price="30">Player — 30€</button>
            <button class="modal-pill"        data-type="long"     data-price="30">Manches longues — 30€</button>
            <button class="modal-pill"        data-type="pro_long" data-price="35">Pro ML — 35€</button>
            <button class="modal-pill"        data-type="enfant"   data-price="25">Enfant — 25€</button>
            <button class="modal-pill"        data-type="retro"    data-price="30">R\u00e9tro — 30€</button>
          </div>
        </div>

        <div class="modal-opt-group">
          <span class="modal-opt-label">Taille</span>
          <div class="modal-pills" id="sizePills">
            <button class="modal-pill" data-size="S">S</button>
            <button class="modal-pill active" data-size="M">M</button>
            <button class="modal-pill" data-size="L">L</button>
            <button class="modal-pill" data-size="XL">XL</button>
            <button class="modal-pill" data-size="XXL">XXL</button>
          </div>
        </div>

        <div class="modal-opt-group">
          <label class="flocage-toggle-row">
            <input type="checkbox" id="flocCheck">
            <span class="flocage-toggle-label">
              <strong>Flocage personnalis\u00e9</strong> (+5€)
              <span class="flocage-free-tag">Offert d\u00e8s 2</span>
            </span>
          </label>
          <div class="flocage-inputs" id="flocInputs">
            <input type="text" class="flocage-input" id="flocName"   placeholder="Nom au dos">
            <input type="text" class="flocage-input" id="flocNumber" placeholder="Num\u00e9ro">
          </div>
        </div>
      </div>

      <div class="modal-foot">
        <div class="modal-price-display" id="modalPrice">25€</div>
        <button class="modal-add-btn" id="modalAddBtn">
          <i class="fa-solid fa-bag-shopping"></i>
          Ajouter au panier
        </button>
      </div>`;
  }

  /* ─────────────────────────────────────────
     CART — RENDER
  ───────────────────────────────────────── */
  function renderCartDrawer() {
    const itemsEl = $('#cartItemsScroll');
    const sumEl   = $('#cartSummaryBox');
    const countEl = $('#cartItemCount');
    if (!itemsEl) return;

    const n = state.cart.items.length;
    if (countEl) countEl.textContent = String(n);

    // Restore persisted inputs
    const igEl    = $('#igInput');
    const emailEl = $('#emailInput');
    if (igEl    && !igEl.value)    igEl.value    = state.cart.ig    || '';
    if (emailEl && !emailEl.value) emailEl.value = state.cart.email || '';

    if (!n) {
      itemsEl.innerHTML = `
        <div class="cart-empty-state">
          <i class="fa-solid fa-bag-shopping"></i>
          <p>Votre panier est vide.<br>Ajoutez des maillots !</p>
        </div>`;
      if (sumEl) sumEl.innerHTML = '';
      return;
    }

    itemsEl.innerHTML = '';
    state.cart.items.forEach((it, idx) => {
      const row = document.createElement('div');
      row.className = 'cart-item-row';
      const flocInfo = it.flocage
        ? `<div class="cart-item-meta">Flocage: ${it.flocName || '—'} #${it.flocNumber || '—'}</div>`
        : '';
      row.innerHTML = `
        <img class="cart-item-thumb" src="${it.src}" alt="${it.team || 'Maillot'}" loading="lazy">
        <div class="cart-item-body">
          <div class="cart-item-team">${it.team || 'Maillot'}</div>
          <div class="cart-item-meta">${categoryLabel(it.type)} &bull; Taille ${it.size}</div>
          ${flocInfo}
          <div class="cart-item-price">${priceForType(it.type)}€${it.flocage ? ` + 5€` : ''}</div>
        </div>
        <button class="cart-item-del" data-remove="${idx}" aria-label="Supprimer">
          <i class="fa-solid fa-xmark"></i>
        </button>`;
      row.querySelector('[data-remove]').addEventListener('click', () => {
        state.cart.items.splice(idx, 1);
        saveCart();
      });
      itemsEl.appendChild(row);
    });

    if (sumEl) {
      const t = cartTotals();
      sumEl.innerHTML = `
        <div class="cart-row"><span>Sous-total</span><span>${t.subtotal}€</span></div>
        <div class="cart-row ${t.offerApplied ? 'promo-row' : ''}">
          <span>Flocage${t.offerApplied ? ' <small>(offert ✓)</small>' : ''}</span>
          <span>${t.flocageTotal}€</span>
        </div>
        <div class="cart-row"><span>Livraison</span><span>${t.delivery}€</span></div>
        <div class="cart-row total-row"><span>Total</span><span>${t.total}€</span></div>`;
    }
  }

  /* ─────────────────────────────────────────
     CART — OPEN / CLOSE
  ───────────────────────────────────────── */
  function openCart() {
    ensureCartDrawer();
    $('#cartDrawer')?.classList.add('open');
    $('#cartBackdrop')?.classList.add('open');
    document.body.style.overflow = 'hidden';
    renderCartDrawer();
  }

  function closeCart() {
    $('#cartDrawer')?.classList.remove('open');
    $('#cartBackdrop')?.classList.remove('open');
    document.body.style.overflow = '';
  }

  /* ─────────────────────────────────────────
     MODAL — OPEN / CLOSE
  ───────────────────────────────────────── */
  function updateModalPrice() {
    const priceEl = $('#modalPrice');
    if (!priceEl) return;
    const basePrice = priceForType(state.modalType);
    const flocage   = $('#flocCheck')?.checked ? PRICES.flocage : 0;
    priceEl.textContent = `${basePrice + flocage}€`;
  }

  function setDefaultTypeForCategory(cat) {
    const typeMap = { fan: 'fan', pro: 'pro', enfant: 'enfant', retro: 'retro' };
    const defType = typeMap[cat] || 'fan';
    $$('#typePills .modal-pill').forEach(p => {
      p.classList.toggle('active', p.dataset.type === defType);
    });
    state.modalType = defType;
  }

  function openAddModal(payload) {
    ensureModal();
    state.addPayload = payload;

    const overlay = $('#addModal');
    const imgEl   = $('#modalImg');
    const teamEl  = $('#modalTeamName');
    if (!overlay) return;

    if (imgEl)  { imgEl.src = payload.src || ''; imgEl.alt = payload.team || 'Maillot'; }
    if (teamEl) teamEl.textContent = payload.team || 'Maillot';

    setDefaultTypeForCategory(payload.category);
    state.modalSize = 'M';
    $$('#sizePills .modal-pill').forEach(p => p.classList.toggle('active', p.dataset.size === 'M'));

    const flocCheck = $('#flocCheck');
    const flocInputs = $('#flocInputs');
    if (flocCheck)  flocCheck.checked = false;
    if (flocInputs) flocInputs.classList.remove('visible');
    $('#flocName'   && '#flocName')   && ($('#flocName').value   = '');
    $('#flocNumber' && '#flocNumber') && ($('#flocNumber').value = '');

    updateModalPrice();
    overlay.classList.add('open');
    document.body.style.overflow = 'hidden';
  }

  function closeAddModal() {
    $('#addModal')?.classList.remove('open');
    document.body.style.overflow = '';
    state.addPayload = null;
  }

  /* ─────────────────────────────────────────
     CART — INIT & EVENT BINDING
  ───────────────────────────────────────── */
  function initCartUI() {
    ensureCartDrawer();
    ensureModal();
    updateCartBadge();

    /* Global click delegation */
    document.body.addEventListener('click', e => {
      /* Add to cart button on product card */
      const addBtn = e.target.closest('[data-add]');
      if (addBtn) {
        e.preventDefault();
        e.stopPropagation();
        try {
          const payload = JSON.parse(addBtn.dataset.add.replace(/&quot;/g, '"'));
          openAddModal(payload);
        } catch {
          openAddModal({
            src:      addBtn.dataset.src || '',
            team:     decodeURIComponent(addBtn.dataset.team || ''),
            category: addBtn.dataset.category || pageCategory() || 'fan',
          });
        }
        return;
      }

      /* Open cart */
      if (e.target.closest('[data-cart-open]')) {
        e.preventDefault();
        openCart();
        return;
      }

      /* Close cart */
      if (e.target.id === 'cartCloseBtn' || e.target.closest('#cartCloseBtn')) {
        closeCart(); return;
      }
      if (e.target.id === 'cartBackdrop') {
        closeCart(); return;
      }

      /* Close modal */
      if (e.target.id === 'addModal' || e.target.id === 'modalImgClose' || e.target.closest('#modalImgClose')) {
        closeAddModal(); return;
      }

      /* Type pill selection */
      const typePill = e.target.closest('#typePills .modal-pill');
      if (typePill) {
        $$('#typePills .modal-pill').forEach(p => p.classList.remove('active'));
        typePill.classList.add('active');
        state.modalType = typePill.dataset.type;
        updateModalPrice();
        return;
      }

      /* Size pill selection */
      const sizePill = e.target.closest('#sizePills .modal-pill');
      if (sizePill) {
        $$('#sizePills .modal-pill').forEach(p => p.classList.remove('active'));
        sizePill.classList.add('active');
        state.modalSize = sizePill.dataset.size;
        return;
      }

      /* Add to cart — modal confirm button */
      if (e.target.id === 'modalAddBtn' || e.target.closest('#modalAddBtn')) {
        const payload    = state.addPayload || {};
        const flocage    = $('#flocCheck')?.checked || false;
        const flocName   = ($('#flocName')?.value   || '').trim() || null;
        const flocNumber = ($('#flocNumber')?.value || '').trim() || null;
        addToCart({
          ...payload,
          type:       state.modalType,
          size:       state.modalSize,
          flocage,
          flocName,
          flocNumber,
          unitPrice:  priceForType(state.modalType),
        });
        closeAddModal();
        return;
      }

      /* Checkout button */
      if (e.target.id === 'checkoutBtn' || e.target.closest('#checkoutBtn')) {
        checkout();
        return;
      }
    });

    /* Flocage toggle */
    document.body.addEventListener('change', e => {
      if (e.target.id === 'flocCheck') {
        $('#flocInputs')?.classList.toggle('visible', e.target.checked);
        updateModalPrice();
      }
    });

    /* Instagram + email persistence */
    document.body.addEventListener('input', e => {
      if (e.target.id === 'igInput')    { state.cart.ig    = e.target.value.trim(); localStorage.setItem('ek_cart', JSON.stringify(state.cart)); }
      if (e.target.id === 'emailInput') { state.cart.email = e.target.value.trim(); localStorage.setItem('ek_cart', JSON.stringify(state.cart)); }
    });

    renderCartDrawer();
  }

  /* ─────────────────────────────────────────
     CHECKOUT
  ───────────────────────────────────────── */
  async function checkout() {
    const ig    = ($('#igInput')?.value    || state.cart.ig    || '').trim();
    const email = ($('#emailInput')?.value || state.cart.email || '').trim();

    if (!ig) {
      showToast('Merci de renseigner votre pseudo Instagram');
      return;
    }
    if (!state.cart.items.length) {
      showToast('Votre panier est vide');
      return;
    }

    const igFollowEl = $('#igFollowCheck');
    if (igFollowEl && !igFollowEl.checked) {
      showToast('Confirmez d\'abord que vous suivez @elitekits.jersey');
      return;
    }

    const checkoutBtn = $('#checkoutBtn');
    if (checkoutBtn) {
      checkoutBtn.disabled = true;
      checkoutBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Envoi en cours...';
    }

    const totals = cartTotals();
    const order  = { instagram: ig, customerEmail: email || null, totals, items: state.cart.items };

    const API_BASE = (window.ELITEKITS_API || '').replace(/\/$/, '');
    const isLocal  = /localhost|127\./.test(location.hostname);
    const endpoint = API_BASE ? `${API_BASE}/api/order` : '/api/order';

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
      showToast(email ? `Commande envoy\u00e9e ! Conf. \u00e0 ${email}` : 'Commande envoy\u00e9e !');
      resetCart(ig, email);
    } catch {
      mailtoFallback(order);
    } finally {
      if (checkoutBtn) {
        checkoutBtn.disabled = false;
        checkoutBtn.innerHTML = '<i class="fa-solid fa-paper-plane"></i> Valider ma commande';
      }
    }
  }

  function mailtoFallback(order) {
    const subject = encodeURIComponent('Nouvelle commande EliteKits');
    const body    = encodeURIComponent(formatOrderText(order));
    window.location.href = `mailto:titouan1502@protonmail.com?subject=${subject}&body=${body}`;
    resetCart(order.instagram, order.customerEmail || '');
  }

  function resetCart(ig, email) {
    state.cart = { items: [], ig: ig || '', email: email || '' };
    saveCart();
    closeCart();
  }

  function formatOrderText(order) {
    const lines = [`Instagram : ${order.instagram}`];
    if (order.customerEmail) lines.push(`Email : ${order.customerEmail}`);
    lines.push('');
    order.items.forEach((it, i) => {
      lines.push(`#${i + 1}  ${it.team || 'Maillot'} | ${it.type} | Taille ${it.size}`);
      if (it.flocage) lines.push(`       Flocage : ${it.flocName || '\u2014'} #${it.flocNumber || '\u2014'}`);
      lines.push(`       Photo : ${location.origin}/${it.src}`);
      lines.push(`       Prix : ${priceForType(it.type)}\u20ac`);
    });
    lines.push('');
    const t = order.totals;
    lines.push(`Sous-total : ${t.subtotal}\u20ac`);
    lines.push(`Flocage    : ${t.flocageTotal}\u20ac${t.offerApplied ? ' (offert)' : ''}`);
    lines.push(`Livraison  : ${t.delivery}\u20ac`);
    lines.push(`TOTAL      : ${t.total}\u20ac`);
    return lines.join('\n');
  }

  /* ─────────────────────────────────────────
     BOOT
  ───────────────────────────────────────── */
  initCartUI();

})();

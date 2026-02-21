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

  // Données metadata.json (fallback CLIP) — vide par défaut si products.json chargé
  let metadata = {};

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
     PRODUCTS DATABASE + SEARCH ENGINE v3.0
     Utilise products.json (données Yupoo scrapées)
     Recherche par nom d'équipe / alias — jamais par couleur
  ───────────────────────────────────────── */
  let products   = [];   // products.json complet
  let searchIndex = [];  // index plat pour la recherche

  // Charger products.json (nouvelle BDD) en priorité,
  // tomber en fallback sur metadata.json (ancienne BDD CLIP)
  const _dataFiles = ['products.json', 'metadata.json'];

  function _loadDataFiles(files, idx = 0) {
    if (idx >= files.length) {
      enhanceProductGrids();
      initCartUI();
      return;
    }
    fetch(files[idx])
      .then(r => { if (!r.ok) throw new Error(); return r.json(); })
      .then(data => {
        const isProducts = Array.isArray(data);
        if (isProducts) {
          products = data || [];
          buildIndexFromProducts();
        } else {
          // Ancien format metadata.json
          metadata = data || {};
          buildIndexFromMetadata(metadata);
        }
        initSearch();
        enhanceProductGrids();
        initCartUI();
      })
      .catch(() => _loadDataFiles(files, idx + 1));
  }

  _loadDataFiles(_dataFiles);

  /* ── Normalisation ─────────────────────────────────────────── */
  function normalizeSrc(path) {
    if (!path) return '';
    if (path.startsWith('http') || path.startsWith('/')) return path;
    if (path.startsWith('images/')) return path;
    return `images/${path}`;
  }

  function normStr(str) {
    return (str || '')
      .toString()
      .normalize('NFD')
      .replace(/\p{Diacritic}/gu, '')
      .toLowerCase()
      .trim();
  }

  function tokenize(str) {
    return normStr(str).split(/[^a-z0-9]+/).filter(Boolean);
  }

  /* ── Construction de l'index depuis products.json ─────────── */
  function buildIndexFromProducts() {
    searchIndex = products.map(p => {
      const src      = p.thumbnail || (p.images && p.images[0]) || '';
      const team     = p.team      || p.team_short || '';
      const teamShort = p.team_short || '';
      const version  = p.version   || 'fan';
      const category = _versionToCategory(version);
      const aliases  = (p.team_aliases || []).filter(a => !_isCJK(a));
      const tags     = p.tags || [];

      // Construire un ensemble de tokens pour la recherche rapide
      const allText = [team, teamShort, ...aliases, ...tags,
                       p.league || '', p.country || '', p.season || ''].join(' ');

      return {
        src,
        team,
        teamShort,
        teamKey:   p.team_key || '',
        category,
        version,
        season:    p.season || '',
        type:      p.type   || '',
        league:    p.league || '',
        country:   p.country || '',
        price:     p.price  || 25,
        aliases,
        tags,
        allText:   normStr(allText),
        tokens:    new Set(tokenize(allText)),
        confidence: p.confidence_score || 0,
        source_url: p.source_url || '',
        product_id: p.id || '',
        matched:   p.matched !== false,
      };
    });
  }

  /* ── Construction de l'index depuis metadata.json (fallback) ─ */
  function buildIndexFromMetadata(metadata) {
    searchIndex = Object.entries(metadata).map(([path, info]) => {
      const src      = normalizeSrc(path);
      const team     = (info && (info.club || info.team)) || '';
      const category = (info && info.category) || _guessCategoryFromPath(path);
      const player   = (info && info.player)   || _guessPlayerFromPath(path);
      const allText  = [team, player, category].join(' ');
      return {
        src, team, teamShort: team, teamKey: normStr(team),
        category, version: category, season: '', type: '', league: '', country: '',
        price: PRICES[category] || 25, aliases: [], tags: [],
        allText: normStr(allText), tokens: new Set(tokenize(allText)),
        confidence: info && info.score || 0, matched: true,
        source_url: '', product_id: '',
      };
    });
  }

  function _versionToCategory(v) {
    const map = { fan: 'fan', player: 'pro', retro: 'retro', kit: 'enfant', enfant: 'enfant' };
    return map[v] || v || 'fan';
  }

  function _guessCategoryFromPath(p) {
    const m = String(p).toLowerCase().split('/')[0];
    if (m === 'player') return 'pro';
    if (m === 'kids')   return 'enfant';
    if (['fan', 'retro'].includes(m)) return m;
    return '';
  }

  function _guessPlayerFromPath(p) {
    const name = String(p).toLowerCase();
    const players = ['messi','ronaldo','mbappe','neymar','haaland','vinicius',
                     'bellingham','griezmann','kane','salah'];
    return players.find(pl => name.includes(pl)) || '';
  }

  function _isCJK(text) {
    return (text || '').split('').filter(c => c >= '\u4e00' && c <= '\u9fff').length >
           (text || '').length * 0.3;
  }

  /* ── Algorithme de recherche ───────────────────────────────── */
  // Ordre de priorité :
  //   1. Exact match sur team_key ou short_name
  //   2. Alias exact (ex: "psg" → Paris Saint-Germain)
  //   3. Contenu dans le nom (startsWith > contains)
  //   4. Tags
  //   5. Fuzzy token-level
  //   JAMAIS de tri par couleur/similarité visuelle

  function rank(query) {
    const q      = query.trim();
    if (!q) return [];
    const qNorm  = normStr(q);
    const qToks  = tokenize(q);
    if (!qToks.length) return [];

    // Détecter des modificateurs dans la requête
    const isHome  = /\b(home|domicile|主场)\b/i.test(q);
    const isAway  = /\b(away|extér|exterieur|客场)\b/i.test(q);
    const isThird = /\b(third|troisième)\b/i.test(q);
    const isRetro = /\b(retro|rétro|vintage)\b/i.test(q);
    const seasonM = q.match(/\b(20\d{2})[/-]?(\d{0,2})\b/);
    const queriedSeason = seasonM ? seasonM[0] : null;

    // Nettoyer la requête de ses modificateurs pour isoler le nom d'équipe
    let teamQuery = qNorm
      .replace(/\b(home|domicile|away|exterieur|extérieur|third|retro|retro|fan|player|maillot|jersey|kit|foot|football|soccer)\b/g, ' ')
      .replace(/20\d{2}[/-]?\d{0,2}/g, ' ')
      .replace(/\s+/g, ' ').trim();

    return searchIndex
      .map(it => {
        let score = 0;

        // ── Filtres contextuels ──────────────────────────────────
        if (isHome   && it.type && it.type !== 'Home')       return null;
        if (isAway   && it.type && it.type !== 'Away')       return null;
        if (isThird  && it.type && it.type !== 'Third')      return null;
        if (isRetro  && it.version !== 'retro')              return null;
        if (queriedSeason && it.season && !it.season.includes(queriedSeason.slice(0,4))) return null;

        const teamNorm  = normStr(it.team);
        const shortNorm = normStr(it.teamShort);

        // ── 1. Exact match sur clé/shortname ────────────────────
        if (teamNorm  === qNorm || shortNorm === qNorm)  score += 200;
        if (it.teamKey === qNorm)                         score += 200;

        // ── 2. Alias exact ──────────────────────────────────────
        if (it.aliases.some(a => normStr(a) === qNorm))  score += 180;

        // ── 3. teamQuery (après nettoyage des modificateurs) ────
        if (teamQuery) {
          if (teamNorm  === teamQuery)               score += 160;
          if (shortNorm === teamQuery)               score += 160;
          if (teamNorm.startsWith(teamQuery))        score +=  80;
          if (teamNorm.includes(teamQuery))          score +=  60;
          if (shortNorm.includes(teamQuery))         score +=  55;
          if (it.aliases.some(a => normStr(a).startsWith(teamQuery))) score += 70;
          if (it.aliases.some(a => normStr(a).includes(teamQuery)))   score += 50;
        }

        // ── 4. Tokens individuels ────────────────────────────────
        let tokenHits = 0;
        for (const tok of qToks) {
          if (tok.length < 2) continue;
          if (it.tokens.has(tok)) {
            score += 30;
            tokenHits++;
          }
          // Match partiel
          if (it.allText.includes(tok)) {
            score += 15;
            tokenHits++;
          }
        }

        // Bonus si tous les tokens sont présents
        if (tokenHits >= qToks.length && qToks.length > 1) score += 40;

        // ── 5. Boost haute confiance ─────────────────────────────
        if (it.matched && it.confidence > 0.85) score += 10;
        if (it.matched && it.confidence > 0.95) score += 10;

        return score > 0 ? { it, score } : null;
      })
      .filter(Boolean)
      .sort((a, b) => b.score - a.score)
      .map(({ it }) => it);
  }

  /* ── Autocomplete API ──────────────────────────────────────── */
  const SEARCH_API = (typeof window !== 'undefined' && window.ELITEKITS_SEARCH_API) || null;
  let _suggestCache = {};
  let _suggestTimer = null;

  function fetchSuggestions(q, callback) {
    if (!q || q.length < 2) { callback([]); return; }

    const cacheKey = q.toLowerCase();
    if (_suggestCache[cacheKey]) { callback(_suggestCache[cacheKey]); return; }

    if (SEARCH_API) {
      // Mode API : appel au serveur FastAPI
      clearTimeout(_suggestTimer);
      _suggestTimer = setTimeout(async () => {
        try {
          const r = await fetch(`${SEARCH_API}/api/suggest?q=${encodeURIComponent(q)}`);
          const d = await r.json();
          const suggestions = (d.suggestions || []).map(s => s.label);
          _suggestCache[cacheKey] = suggestions;
          callback(suggestions);
        } catch { callback([]); }
      }, 300);
    } else {
      // Mode client-side : extraire depuis l'index local
      const qn = normStr(q);
      const seen = new Set();
      const suggestions = [];
      for (const it of searchIndex) {
        if (seen.has(it.teamKey) || !it.teamKey) continue;
        const sn = normStr(it.teamShort);
        const tn = normStr(it.team);
        if (sn.startsWith(qn) || tn.startsWith(qn) || sn.includes(qn)) {
          seen.add(it.teamKey);
          suggestions.push(it.team);
          if (suggestions.length >= 8) break;
        }
      }
      _suggestCache[cacheKey] = suggestions;
      callback(suggestions);
    }
  }

  /* ─────────────────────────────────────────
     SEARCH UI
  ───────────────────────────────────────── */
  function initSearch() {
    const input    = $('#searchInput');
    const clearBtn = $('#searchClear');
    if (!input) return;

    // Créer le dropdown d'autocomplete
    const dropdown = _ensureAutocomplete(input);

    let _searchTimer = null;
    input.addEventListener('input', e => {
      const q = e.target.value.trim();
      if (clearBtn) clearBtn.classList.toggle('visible', q.length > 0);
      if (!q) { hideResults(); _hideDropdown(dropdown); return; }

      // Autocomplete (debounce 300ms)
      fetchSuggestions(q, items => _renderDropdown(dropdown, items, input));

      // Résultats de recherche (debounce 150ms pour fluidité)
      clearTimeout(_searchTimer);
      _searchTimer = setTimeout(() => {
        const results = rank(q);
        state.allResults = results;
        applyFilterAndRender();
      }, 150);
    });

    // Clear button
    clearBtn?.addEventListener('click', () => {
      input.value = '';
      clearBtn.classList.remove('visible');
      hideResults();
      _hideDropdown(dropdown);
    });

    // Fermer le dropdown si clic ailleurs
    document.addEventListener('click', e => {
      if (!input.contains(e.target) && !dropdown.contains(e.target)) {
        _hideDropdown(dropdown);
      }
    });

    // Keyboard navigation dans le dropdown
    input.addEventListener('keydown', e => {
      const items = $$('.ac-item', dropdown);
      const active = $('.ac-item.ac-active', dropdown);
      if (!items.length) return;
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        const next = active ? (items.indexOf(active) + 1) % items.length : 0;
        items.forEach(i => i.classList.remove('ac-active'));
        items[next].classList.add('ac-active');
        input.value = items[next].textContent;
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        const prev = active ? (items.indexOf(active) - 1 + items.length) % items.length : items.length - 1;
        items.forEach(i => i.classList.remove('ac-active'));
        items[prev].classList.add('ac-active');
        input.value = items[prev].textContent;
      } else if (e.key === 'Enter') {
        if (active) {
          input.value = active.textContent;
          _hideDropdown(dropdown);
          const results = rank(input.value);
          state.allResults = results;
          applyFilterAndRender();
        }
      } else if (e.key === 'Escape') {
        _hideDropdown(dropdown);
      }
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

  /* ── Autocomplete dropdown ─────────────────────────────────── */
  function _ensureAutocomplete(input) {
    let dropdown = $('#searchAutocomplete');
    if (dropdown) return dropdown;

    dropdown = document.createElement('div');
    dropdown.id = 'searchAutocomplete';
    dropdown.style.cssText = [
      'position:absolute', 'z-index:999', 'background:rgba(10,10,28,0.98)',
      'border:1px solid rgba(124,58,237,0.5)', 'border-radius:10px',
      'box-shadow:0 8px 32px rgba(0,0,0,0.5)', 'display:none',
      'min-width:260px', 'overflow:hidden', 'backdrop-filter:blur(8px)',
    ].join(';');

    const wrap = input.closest('.search-wrap, .search-bar-wrap, .header-search') || input.parentElement;
    wrap.style.position = 'relative';
    wrap.appendChild(dropdown);
    return dropdown;
  }

  function _renderDropdown(dropdown, items, input) {
    if (!items || !items.length) { _hideDropdown(dropdown); return; }
    dropdown.innerHTML = items.map(label =>
      `<div class="ac-item" style="padding:0.65rem 1rem;cursor:pointer;font-size:0.9rem;color:#e2e8f0;
        transition:background 0.15s;display:flex;align-items:center;gap:0.5rem">
        <i class="fa-solid fa-magnifying-glass" style="color:#7c3aed;font-size:0.75rem;opacity:0.7"></i>
        ${_escHtml(label)}
      </div>`
    ).join('');

    $$('.ac-item', dropdown).forEach((el, i) => {
      el.addEventListener('mouseenter', () => {
        $$('.ac-item', dropdown).forEach(x => x.classList.remove('ac-active'));
        el.classList.add('ac-active');
        el.style.background = 'rgba(124,58,237,0.2)';
      });
      el.addEventListener('mouseleave', () => {
        el.classList.remove('ac-active');
        el.style.background = '';
      });
      el.addEventListener('mousedown', e => {
        e.preventDefault();
        input.value = items[i];
        _hideDropdown(dropdown);
        $('#searchClear')?.classList.add('visible');
        const results = rank(items[i]);
        state.allResults = results;
        applyFilterAndRender();
      });
    });

    dropdown.style.display = 'block';
  }

  function _hideDropdown(dropdown) {
    if (dropdown) dropdown.style.display = 'none';
  }

  function _escHtml(str) {
    return String(str)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
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

    const teamLabel = item.teamShort || item.team || 'Maillot';
    const cat       = item.category  || 'fan';
    const season    = item.season    || '';
    const type      = item.type      || '';
    const typeLabel = _typeLabel(type);
    const subtitle  = [typeLabel, season].filter(Boolean).join(' \u00b7 ');

    const addDataStr = JSON.stringify({
      src:      item.src,
      team:     teamLabel,
      category: cat,
    }).replace(/"/g, '&quot;');

    card.innerHTML = `
      <div class="product-card-img">
        <img src="${item.src}" alt="${teamLabel}" loading="lazy"
             onerror="this.src='';this.onerror=null">
        <span class="product-badge ${categoryBadgeClass(cat)}">${categoryLabel(cat)}</span>
        <button class="product-card-add" data-add="${addDataStr}" aria-label="Ajouter au panier">
          <i class="fa-solid fa-plus"></i>
        </button>
      </div>
      <div class="product-card-info">
        <div class="product-team">${teamLabel}</div>
        ${subtitle ? `<div class="product-player">${subtitle}</div>` : ''}
        <div class="product-price"><span class="from">d\u00e8s</span> ${startingPrice(cat)}</div>
      </div>`;
    return card;
  }

  function _typeLabel(type) {
    const map = {
      'Home': 'Domicile', 'Away': 'Ext\u00e9rieur',
      'Third': 'Third',   'Goalkeeper': 'Gardien',
      'Training': 'Training', 'Special': '\u00c9d. Sp\u00e9ciale',
    };
    return map[type] || type || '';
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
      const info = (key && metadata && metadata[key]) || {};
      return {
        src,
        team:     info.club || info.team || '',
        category: cat || info.category || _guessCategoryFromPath(src || ''),
        player:   info.player || _guessPlayerFromPath(src || ''),
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

export function normalize(value) {
  return String(value ?? '').normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase().replace(/\s+/g, ' ').trim();
}

export function parseFilters(search, taxonomy, vendors) {
  const params = new URLSearchParams(search);
  const categoryIds = new Set(taxonomy.categories.map(item => item.id));
  const topicIds = new Set(taxonomy.topics.map(item => item.id));
  return {
    query: (params.get('q') ?? '').slice(0, 300),
    category: categoryIds.has(params.get('category')) ? params.get('category') : '',
    vendor: vendors.includes(params.get('vendor')) ? params.get('vendor') : '',
    topics: [...new Set(params.getAll('topic').filter(topic => topicIds.has(topic)))],
  };
}

export function serializeFilters(filters) {
  const params = new URLSearchParams();
  if (filters.query.trim()) params.set('q', filters.query.trim());
  if (filters.category) params.set('category', filters.category);
  if (filters.vendor) params.set('vendor', filters.vendor);
  for (const topic of [...filters.topics].sort()) params.append('topic', topic);
  const query = params.toString();
  return query ? `?${query}` : '';
}

export function matchesFilters(deal, filters) {
  const words = normalize(filters.query).split(' ').filter(Boolean);
  const haystack = normalize([deal.vendor, deal.product, deal.description, deal.coupon, ...(deal.topics ?? []), deal.search_text ?? ''].join(' '));
  return words.every(word => haystack.includes(word))
    && (!filters.category || deal.category === filters.category)
    && (!filters.vendor || deal.vendor === filters.vendor)
    && (!filters.topics.length || filters.topics.some(topic => deal.topics?.includes(topic)));
}

export function freshness(value, now = Date.now()) {
  const timestamp = Date.parse(value);
  if (!Number.isFinite(timestamp) || timestamp > now + 5 * 60_000) return 'unknown';
  return now - timestamp > 3 * 60 * 60_000 ? 'stale' : 'fresh';
}

export function relativeTime(value, now = Date.now()) {
  const timestamp = Date.parse(value);
  if (!Number.isFinite(timestamp) || timestamp > now + 5 * 60_000) return 'Confirmation unavailable';
  const minutes = Math.max(0, Math.floor((now - timestamp) / 60_000));
  if (minutes < 1) return 'Checked just now';
  if (minutes < 60) return `Checked ${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 48) return `Checked ${hours}h ago`;
  return `Checked ${Math.floor(hours / 24)}d ago`;
}

export function offerAvailability(deal, now = Date.now()) {
  if (deal.ends_at && Number.isFinite(Date.parse(deal.ends_at)) && Date.parse(deal.ends_at) <= now) return 'expired';
  // A vendor date without a time zone, once it has passed in every time zone.
  if (deal.expiry_cutoff_at && Number.isFinite(Date.parse(deal.expiry_cutoff_at)) && Date.parse(deal.expiry_cutoff_at) <= now) return 'expired';
  // Beyond November in every civil time zone; not a fabricated seller deadline.
  if (deal.expiry_label === 'November 2026 only' && now >= Date.parse('2026-12-02T00:00:00Z')) return 'expired';
  if (deal.starts_at && Number.isFinite(Date.parse(deal.starts_at)) && Date.parse(deal.starts_at) > now) return 'upcoming';
  return 'current';
}

export function offerStatus(deal, now = Date.now()) {
  const upcoming = offerAvailability(deal, now) === 'upcoming';
  if (freshness(deal.last_offer_confirmed_at, now) !== 'fresh') return upcoming ? 'Upcoming · Recheck pending' : 'Recheck pending';
  return upcoming ? 'Upcoming' : deal.marketplace ? 'Marketplace-published' : 'Vendor-published';
}

export function orderDeals(deals, now = Date.now()) {
  return [...deals].sort((a, b) => {
    const staleA = freshness(a.last_offer_confirmed_at, now) !== 'fresh';
    const staleB = freshness(b.last_offer_confirmed_at, now) !== 'fresh';
    return Number(staleA) - Number(staleB)
      || (Date.parse(b.first_seen_at) || 0) - (Date.parse(a.first_seen_at) || 0)
      || a.product.localeCompare(b.product);
  });
}

function startDirectory() {
  const stateElement = document.getElementById('page-state');
  if (!stateElement) return;
  let state;
  try { state = JSON.parse(stateElement.textContent); } catch { return; }
  const searchInput = document.getElementById('search');
  const categoryInput = document.getElementById('category');
  const vendorInput = document.getElementById('vendor');
  const topicInputs = [...document.querySelectorAll('input[name="topic"]')];
  const grid = document.getElementById('deal-grid');
  const initialDealCount = state.deals.length;
  const cardById = new Map([...grid.querySelectorAll('.deal-card')].map(card => [card.dataset.dealId, card]));
  let filters = parseFilters(location.search, state.taxonomy, state.vendors);
  let toastTimer;
  const topicLabels = Object.fromEntries(state.taxonomy.topics.map(item => [item.id, item.label]));
  const categoryLabels = Object.fromEntries(state.taxonomy.categories.map(item => [item.id, item.label]));

  function announce(message) {
    const toast = document.getElementById('toast');
    clearTimeout(toastTimer);
    toast.textContent = message;
    toast.classList.add('is-visible');
    toastTimer = setTimeout(() => toast.classList.remove('is-visible'), 3000);
  }

  function syncInputs() {
    searchInput.value = filters.query;
    categoryInput.value = filters.category;
    vendorInput.value = filters.vendor;
    topicInputs.forEach(input => { input.checked = filters.topics.includes(input.value); });
    if (filters.topics.some(topic => topic.includes('-security') && ['llm-security', 'agent-security', 'mcp-security'].includes(topic))) {
      const specialties = document.querySelector('.more-topics');
      if (specialties) specialties.open = true;
    }
  }

  function renderChips() {
    const holder = document.getElementById('active-filters');
    holder.replaceChildren();
    const chips = [];
    if (filters.query.trim()) chips.push({ label: `Search: ${filters.query}`, type: 'query' });
    if (filters.category) chips.push({ label: categoryLabels[filters.category], type: 'category' });
    if (filters.vendor) chips.push({ label: filters.vendor, type: 'vendor' });
    filters.topics.forEach(topic => chips.push({ label: topicLabels[topic], type: 'topic', value: topic }));
    for (const chip of chips) {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'active-chip';
      button.textContent = chip.label;
      button.setAttribute('aria-label', `Remove filter: ${chip.label}`);
      const x = document.createElement('span');
      x.textContent = '×';
      x.setAttribute('aria-hidden', 'true');
      button.append(x);
      button.addEventListener('click', () => {
        if (chip.type === 'topic') filters.topics = filters.topics.filter(topic => topic !== chip.value);
        else filters[chip.type] = '';
        syncInputs();
        render(true);
      });
      holder.append(button);
    }
    document.getElementById('active-count').textContent = chips.length ? `(${chips.length})` : '';
  }

  function updateFreshness(now) {
    let staleCount = 0;
    for (const deal of state.deals) {
      const card = cardById.get(deal.id);
      if (!card) continue;
      const status = freshness(deal.last_offer_confirmed_at, now);
      const availability = offerAvailability(deal, now);
      const isStale = status !== 'fresh';
      const badge = card.querySelector('[data-status]');
      const upcomingWarning = card.querySelector('[data-upcoming-warning]');
      if (upcomingWarning) upcomingWarning.hidden = availability !== 'upcoming';
      card.classList.toggle('deal-card--stale', isStale);
      badge.classList.toggle('status-badge--stale', isStale);
      badge.textContent = offerStatus(deal, now);
      card.dataset.stale = String(isStale);
      const checked = card.querySelector('[data-relative-time]');
      checked.textContent = relativeTime(deal.last_offer_confirmed_at, now);
      if (isStale && availability !== 'expired') staleCount++;
    }
    const warning = document.getElementById('stale-notice');
    warning.hidden = !staleCount;
    warning.textContent = `${staleCount} offer${staleCount === 1 ? ' needs' : 's need'} a recheck. Last-known information is retained and clearly marked.`;
    const lastRun = state.collection.last_completed_at;
    const collectionTime = document.getElementById('collection-time');
    if (lastRun && Number.isFinite(Date.parse(lastRun))) {
      collectionTime.dateTime = lastRun;
      collectionTime.textContent = `${new Intl.DateTimeFormat('en-GB', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit', timeZone: 'UTC' }).format(new Date(lastRun))} UTC`;
    }
    const collectionStale = freshness(lastRun, now) !== 'fresh';
    const hasFailures = state.collection.failed_sources > 0;
    document.getElementById('collection-dot').classList.toggle('live-dot--stale', collectionStale || hasFailures);
    if (collectionStale && lastRun) document.getElementById('collection-note').textContent = 'Last-known collection · recheck pending';
  }

  function render(updateUrl = false) {
    const now = Date.now();
    updateFreshness(now);
    let visibleCount = 0;
    for (const deal of orderDeals(state.deals, now)) {
      const card = cardById.get(deal.id);
      if (!card) continue;
      const visible = offerAvailability(deal, now) !== 'expired' && matchesFilters(deal, filters);
      card.hidden = !visible;
      if (visible) visibleCount++;
      grid.append(card);
    }
    document.getElementById('result-count').textContent = String(visibleCount);
    const hasFilters = filters.query || filters.category || filters.vendor || filters.topics.length;
    document.getElementById('result-caption').textContent = hasFilters
      ? `${visibleCount} matching offer${visibleCount === 1 ? '' : 's'} · Filters applied locally`
      : `${state.vendors.length} vendor${state.vendors.length === 1 ? '' : 's'} · Original-currency prices · Source links included`;
    const empty = document.getElementById('empty-results');
    empty.hidden = visibleCount > 0;
    if (!visibleCount && initialDealCount) {
      empty.querySelector('h3').textContent = 'No offers match those filters';
      empty.querySelector('p').textContent = 'Try a broader search or clear your filters.';
    }
    document.getElementById('results-end-text').textContent = visibleCount
      ? 'You’re all caught up. Better security starts with informed choices.'
      : 'Only evidence-supported offers will appear here.';
    renderChips();
    if (updateUrl) history.replaceState(null, '', location.pathname + serializeFilters(filters));
  }

  syncInputs();
  render();
  searchInput.addEventListener('input', () => { filters.query = searchInput.value.slice(0, 300); render(true); });
  categoryInput.addEventListener('change', () => { filters.category = categoryInput.value; render(true); });
  vendorInput.addEventListener('change', () => { filters.vendor = vendorInput.value; render(true); });
  topicInputs.forEach(input => input.addEventListener('change', () => {
    filters.topics = topicInputs.filter(item => item.checked).map(item => item.value);
    render(true);
  }));
  document.querySelector('.search-form').addEventListener('submit', event => { event.preventDefault(); render(true); });
  document.querySelectorAll('[data-reset]').forEach(button => button.addEventListener('click', () => {
    filters = { query: '', category: '', vendor: '', topics: [] };
    syncInputs(); render(true);
  }));
  document.addEventListener('keydown', event => {
    if (event.key === '/' && !event.ctrlKey && !event.metaKey && !event.altKey && !['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement?.tagName) && !document.activeElement?.isContentEditable) {
      event.preventDefault(); searchInput.focus();
    }
  });
  const filterToggle = document.querySelector('.mobile-filter-toggle');
  filterToggle.addEventListener('click', () => {
    const expanded = filterToggle.getAttribute('aria-expanded') !== 'true';
    filterToggle.setAttribute('aria-expanded', String(expanded));
    document.getElementById('filter-controls').classList.toggle('is-open', expanded);
  });
  window.addEventListener('popstate', () => { filters = parseFilters(location.search, state.taxonomy, state.vendors); syncInputs(); render(); });
  grid.addEventListener('click', async event => {
    const button = event.target.closest('[data-copy]');
    if (!button) return;
    const code = button.dataset.copy;
    try {
      if (!navigator.clipboard?.writeText) throw new Error('Clipboard unavailable');
      await navigator.clipboard.writeText(code);
      announce(`Copied ${code}`);
    } catch {
      announce(`Could not copy automatically. Coupon: ${code}`);
      const selection = window.getSelection();
      const range = document.createRange();
      range.selectNodeContents(button.querySelector('.coupon-code'));
      selection?.removeAllRanges(); selection?.addRange(range);
    }
  });
  setInterval(() => render(), 60_000);

  async function checkForSnapshot() {
    if (document.hidden) return;
    try {
      const response = await fetch('/data/snapshot.json', { cache: 'no-cache', credentials: 'omit' });
      if (!response.ok || !(response.headers.get('content-type') ?? '').includes('json')) return;
      const latest = await response.json();
      if (latest.schema_version !== 1 || latest.edition !== 2026 || !Array.isArray(latest.deals)) return;
      const latestTime = Date.parse(latest.generated_at);
      if (Number.isFinite(latestTime) && latestTime > Date.parse(state.generated_at)) {
        const active = document.activeElement;
        if (active?.tagName === 'INPUT' || document.querySelector('.offer-details[open]')) {
          announce('New source information is available. Refresh when you’re ready.');
        } else {
          const url = location.pathname + serializeFilters(filters);
          location.replace(url);
        }
      }
    } catch { /* Keep the static last-known-good page on connectivity failure. */ }
  }
  setInterval(checkForSnapshot, 5 * 60_000);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) { render(); checkForSnapshot(); } });
}

if (typeof document !== 'undefined') startDirectory();

(() => {
  const cards = [...document.querySelectorAll('[data-finding]')];
  const search = document.querySelector('#search');
  const sector = document.querySelector('#sector');
  function filter() {
    const q = (search?.value || '').toLowerCase().trim();
    let count = 0;
    cards.forEach(card => {
      const show = (!q || card.textContent.toLowerCase().includes(q)) && (!sector?.value || card.dataset.sector === sector.value);
      card.hidden = !show;
      if (show) count++;
    });
    const result = document.querySelector('#filter-count');
    if (result) result.textContent = `${count} ${count === 1 ? 'story' : 'stories'} shown`;
    const empty = document.querySelector('#no-results');
    if (empty) empty.hidden = count > 0;
  }
  search?.addEventListener('input', filter);
  sector?.addEventListener('change', filter);
  if (sector) {
    const requested = new URLSearchParams(location.search).get('sector');
    if ([...sector.options].some(option => option.value === requested)) sector.value = requested;
    filter();
  }
  const dialog = document.querySelector('#share-dialog');
  const text = document.querySelector('#share-text');
  const message = document.querySelector('#share-message');
  let active = null;
  let trigger = null;
  document.querySelectorAll('[data-share]').forEach(button => button.addEventListener('click', () => {
    trigger = button;
    const base = JSON.parse(button.dataset.share);
    active = {...base};
    text.value = `${active.title}\n\n${active.summary}\n\nStatus: ${active.status}\nLimit: ${active.boundary}\n\n${active.url}`;
    message.textContent = '';
    dialog.querySelector('[data-destination=email]').href = `mailto:?subject=${encodeURIComponent(active.title)}&body=${encodeURIComponent(text.value)}`;
    const encoded = encodeURIComponent(active.url);
    dialog.querySelector('[data-destination=facebook]').href = `https://www.facebook.com/sharer/sharer.php?u=${encoded}`;
    dialog.querySelector('[data-destination=linkedin]').href = `https://www.linkedin.com/sharing/share-offsite/?url=${encoded}`;
    dialog.showModal();
  }));
  document.querySelector('#close-share')?.addEventListener('click', () => dialog.close());
  dialog?.addEventListener('close', () => trigger?.focus());
  dialog?.addEventListener('click', event => {
    if (event.target === dialog) {
      const r = dialog.getBoundingClientRect();
      if (event.clientX < r.left || event.clientX > r.right || event.clientY < r.top || event.clientY > r.bottom) dialog.close();
    }
  });
  text?.addEventListener('input', () => {
    if (active) dialog.querySelector('[data-destination=email]').href = `mailto:?subject=${encodeURIComponent(active.title)}&body=${encodeURIComponent(text.value)}`;
  });
  async function copy(value) {
    try { await navigator.clipboard.writeText(value); message.textContent = 'Copied to clipboard.'; }
    catch { text.focus(); text.select(); message.textContent = 'Clipboard unavailable. Select and copy the text above.'; }
  }
  document.querySelector('#copy-post')?.addEventListener('click', () => copy(text.value));
  document.querySelector('#copy-link')?.addEventListener('click', () => copy(active.url));
  document.querySelector('#native-share')?.addEventListener('click', async () => {
    if (!navigator.share) { await copy(text.value); return; }
    try { await navigator.share({title: active.title, text: text.value}); }
    catch (error) { if (error.name !== 'AbortError') message.textContent = 'Sharing unavailable. Copy the post or link instead.'; }
  });
  document.querySelector('#print-finding')?.addEventListener('click', () => window.print());
})();

// Include references in printed articles, then restore each reader's disclosure state.
(() => {
  let previouslyOpen = [];
  addEventListener('beforeprint', () => {
    previouslyOpen = [...document.querySelectorAll('details.references')].map(node => [node, node.open]);
    previouslyOpen.forEach(([node]) => { node.open = true; });
  });
  addEventListener('afterprint', () => {
    previouslyOpen.forEach(([node, open]) => { node.open = open; });
    previouslyOpen = [];
  });
})();

// Same-page timeline remains keyboard navigable; observer highlights the story in view.
const watchLinks = [...document.querySelectorAll('[data-watch-link]')];
if (watchLinks.length && 'IntersectionObserver' in window) {
  const observer = new IntersectionObserver(entries => {
    entries.filter(e => e.isIntersecting).forEach(entry => {
      watchLinks.forEach(link => {
        if (link.dataset.watchLink === entry.target.dataset.watchStory) link.setAttribute('aria-current', 'true');
        else link.removeAttribute('aria-current');
      });
    });
  }, {rootMargin: '-140px 0px -55% 0px', threshold: 0});
  document.querySelectorAll('[data-watch-story]').forEach(story => observer.observe(story));
}
// Fetch only our published snapshot, never visitor-side requests to third parties.
const statusPanel = document.querySelector('[data-status-url]');
async function refreshIndicators() {
  if (!statusPanel) return;
  try {
    const response = await fetch(statusPanel.dataset.statusUrl, {cache: 'no-store'});
    if (!response.ok) throw new Error('Snapshot unavailable');
    const data = await response.json();
    if (![1, 2].includes(data.schema_version) || !Array.isArray(data.items)) throw new Error('Unknown status format');
    data.items.forEach(item => {
      const node = [...statusPanel.querySelectorAll('[data-indicator]')].find(n => n.dataset.indicator === item.id);
      if (!node) return;
      const historical = item.state !== 'verified' && item.last_verified;
      const reading = historical || item;
      const verified = Date.parse(reading.verified_at || '');
      const deadlines = [reading.valid_until, reading.review_due].map(value => Date.parse(value || '')).filter(Number.isFinite);
      const deadline = deadlines.length ? Math.min(...deadlines) : NaN;
      const expired = (item.state === 'verified' || historical) && Number.isFinite(deadline) && Date.now() >= deadline;
      const stale = (item.state === 'verified' || historical) && (!Number.isFinite(verified) || Date.now() - verified > data.stale_after_hours * 3600000 || verified > Date.now() + 300000);
      const note = [...statusPanel.querySelectorAll('[data-indicator-note]')].find(n => n.dataset.indicatorNote === item.id);
      if (note) {
        note.textContent = item.label + ': ' + item.note + ' ';
        if (item.source_url && /^https:\/\//.test(item.source_url)) {
          const link = document.createElement('a');
          link.href = item.source_url; link.rel = 'noreferrer'; link.textContent = 'Official source ↗'; note.append(link);
        }
      }
      if (item.id === 'dhs' && note) {
        const link = document.createElement('a'); link.href = 'https://www.dhs.gov/national-terrorism-advisory-system'; link.textContent = ' DHS advisory page ↗'; note.append(link);
      }
      if (note && item.review_due) {
        const review = document.createElement('p'); review.textContent = 'Source review due: ' + new Date(item.review_due).toLocaleString('en-US', {timeZone:'America/New_York', timeZoneName:'short'}) + '. Editorial deadline, not official policy expiration.'; note.append(review);
      }
      if (note && item.last_verified) {
        const last = document.createElement('p'); last.textContent = 'Last verified: ' + item.last_verified.value + ' (' + new Date(item.last_verified.verified_at).toLocaleString('en-US', {timeZone:'America/New_York', timeZoneName:'short'}) + '). Historical, not a current reading.'; note.append(last);
      }
      if (note && Array.isArray(item.advisories)) item.advisories.forEach(advisory => {
        try {
          const url = new URL(advisory.url);
          if (url.protocol !== 'https:' || !['dhs.gov', 'www.dhs.gov'].includes(url.hostname) || url.username) return;
          const p = document.createElement('p'); const link = document.createElement('a'); link.href = url.href; link.rel = 'noreferrer'; link.textContent = advisory.summary; p.append(link);
          const expires = new Date(advisory.expires_at).toLocaleString('en-US', {timeZone:'America/New_York', timeZoneName:'short'});
          p.append(' · ' + advisory.type + ' · expires ' + expires + '.'); note.append(p);
        } catch (_) { /* malformed advisory links are never rendered */ }
      });
      ['verified','unavailable','not_disclosed','source_blocked','retrieval_failed','needs_review','stale','expired','last_verified'].forEach(state => node.classList.remove(state));
      node.classList.add(expired ? 'expired' : stale ? 'stale' : historical ? 'last_verified' : item.state);
      let health = node.querySelector('.indicator-health');
      if (historical) {
        if (!health) { health = document.createElement('small'); health.className = 'indicator-health'; node.querySelector('.indicator-value').parentNode.append(health); }
        health.textContent = ({source_blocked:'Update blocked', retrieval_failed:'Update failed', needs_review:'Update needs review'})[item.state] || '';
      } else health?.remove();
      if (item.id === 'uk') {
        const level = ['LOW','MODERATE','SUBSTANTIAL','SEVERE','CRITICAL'].indexOf(item.value) + 1;
        let bars = node.querySelector('.status-bars');
        if (level && !bars) {
          bars = document.createElement('span'); bars.className = 'status-bars'; bars.setAttribute('aria-hidden', 'true');
          for (let i=0;i<5;i++) bars.append(document.createElement('i'));
          node.querySelector('.status-glyph')?.remove(); node.prepend(bars);
        }
        if (bars) [...bars.children].forEach((bar, index) => bar.classList.toggle('on', index < level));
      }
      node.querySelector('.indicator-value').textContent = expired ? (reading.valid_until ? 'Advisory update required' : 'Source review due') : stale ? 'Stale · ' + reading.value : historical ? reading.value + ' · last verified' : item.value;
    });
    const time = statusPanel.querySelector('[data-status-checked]');
    time.dateTime = data.checked_at;
    time.textContent = new Date(data.checked_at).toLocaleString('en-US', {timeZone:'America/New_York', timeZoneName:'short'});
  } catch (_) {
    statusPanel.querySelectorAll('[data-indicator]').forEach(node => {
      if (node.dataset.indicator === 'defcon') return;
      node.classList.remove('verified'); node.classList.add('retrieval_failed');
      node.querySelector('.indicator-value').textContent = 'Snapshot unavailable';
    });
  }
}
refreshIndicators();
setInterval(refreshIndicators, 300000);

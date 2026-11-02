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
    if (data.schema_version !== 1 || !Array.isArray(data.items)) throw new Error('Unknown status format');
    data.items.forEach(item => {
      const node = [...statusPanel.querySelectorAll('[data-indicator]')].find(n => n.dataset.indicator === item.id);
      if (!node) return;
      const verified = Date.parse(item.verified_at || '');
      const stale = item.state === 'verified' && (!Number.isFinite(verified) || Date.now() - verified > data.stale_after_hours * 3600000 || verified > Date.now() + 300000);
      const note = [...statusPanel.querySelectorAll('[data-indicator-note]')].find(n => n.dataset.indicatorNote === item.id);
      if (note) {
        note.textContent = item.label + ': ' + item.note + ' ';
        if (item.source_url && /^https:\/\//.test(item.source_url)) {
          const link = document.createElement('a');
          link.href = item.source_url; link.rel = 'noreferrer'; link.textContent = 'Official source ↗'; note.append(link);
        }
      }
      node.classList.toggle('stale', stale);
      node.classList.toggle('unavailable', item.state !== 'verified');
      node.querySelector('.indicator-value').textContent = stale ? 'Stale · ' + item.value : item.value;
    });
    const time = statusPanel.querySelector('[data-status-checked]');
    time.dateTime = data.checked_at;
    time.textContent = data.checked_at.slice(0, 16).replace('T', ' ') + ' UTC';
  } catch (_) {
    statusPanel.querySelectorAll('.indicator-value').forEach(node => { node.textContent = 'Snapshot unavailable'; });
  }
}
refreshIndicators();
setInterval(refreshIndicators, 300000);

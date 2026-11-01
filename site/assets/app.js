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
    if (result) result.textContent = `${count} finding${count === 1 ? '' : 's'} shown`;
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

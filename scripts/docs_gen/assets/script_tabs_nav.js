
  /* Side panel: highlights the section in view, shows reading progress, collapses to a top bar on narrow screens */
  (() => {
    const nav = document.getElementById('sidenav');
    if (!nav) return;
    const list = nav.querySelector('.sn-list');
    const links = [...list.querySelectorAll('a[href^="#"]')];
    const pairs = links.map((a) => [a, document.getElementById(a.getAttribute('href').slice(1))]).filter((p) => p[1]);
    links.forEach((a) => { a.title = a.textContent.replace(/\s+/g, ' ').trim(); });
    const curPart = nav.querySelector('.sn-cur-part');
    const current = nav.querySelector('.sn-current');
    const fill = nav.querySelector('.sn-progress span');
    const readbar = document.querySelector('.readbar span');
    const toggle = nav.querySelector('.sn-toggle');
    let activeLink = null;
    let ticking = false;

    const update = () => {
      ticking = false;
      const line = Math.min(160, window.innerHeight * 0.3);
      const max = document.documentElement.scrollHeight - window.innerHeight;
      let pick = pairs[0];
      for (const p of pairs) {
        if (p[1].getBoundingClientRect().top - line <= 0) pick = p; else break;
      }
      if (max > 0 && window.scrollY >= max - 2) pick = pairs[pairs.length - 1];
      const pct = max > 0 ? Math.min(100, Math.max(0, (window.scrollY / max) * 100)) : 0;
      fill.style.width = pct + '%';
      if (readbar) readbar.style.width = pct + '%';
      if (!pick || pick[0] === activeLink) return;
      if (activeLink) { activeLink.classList.remove('is-active'); activeLink.removeAttribute('aria-current'); }
      activeLink = pick[0];
      activeLink.classList.add('is-active');
      activeLink.setAttribute('aria-current', 'location');
      const partLi = activeLink.closest('.sn-part');
      nav.querySelectorAll('.sn-part').forEach((p) => p.classList.toggle('is-active', p === partLi));
      const isSub = activeLink.closest('ol') !== list;
      curPart.textContent = isSub && partLi ? partLi.dataset.name : '';
      current.textContent = activeLink.textContent.replace(/\s+/g, ' ').trim();
      const colour = partLi ? getComputedStyle(partLi).getPropertyValue('--part').trim() : '';
      if (colour) document.documentElement.style.setProperty('--now', colour);
      if (getComputedStyle(list).display !== 'none' && nav.scrollHeight > nav.clientHeight + 4) {
        const n = nav.getBoundingClientRect();
        const r = activeLink.getBoundingClientRect();
        if (r.top < n.top + 150 || r.bottom > n.bottom - 24) nav.scrollTop += r.top - n.top - n.height / 2;
      }
    };

    toggle.addEventListener('click', () => {
      const open = !nav.classList.contains('is-open');
      nav.classList.toggle('is-open', open);
      toggle.setAttribute('aria-expanded', String(open));
    });
    list.addEventListener('click', (event) => {
      if (event.target.closest('a') && nav.classList.contains('is-open')) {
        nav.classList.remove('is-open');
        toggle.setAttribute('aria-expanded', 'false');
      }
    });
    window.addEventListener('scroll', () => {
      if (!ticking) { ticking = true; requestAnimationFrame(update); }
    }, { passive: true });
    window.addEventListener('resize', update);
    update();
  })();

(function(){
  var MQ = '(max-width:1100px)';

  function navPath(raw){
    var p = (raw || '/').split('?')[0].split('#')[0];
    try { p = decodeURIComponent(p); } catch (e) {}
    p = p.replace(/\.html$/i, '');
    if (p.length > 1) p = p.replace(/\/+$/, '');
    if (p === '/es') p = '/';
    else if (p.indexOf('/es/') === 0) p = p.slice(3);
    if (!p) p = '/';
    return p;
  }

  function isEsHost(){
    return /(^|\.)es\.agentmedicarehub\.com$/i.test(location.hostname);
  }

  function isLocalHost(){
    var h = location.hostname;
    return h === 'localhost' || h === '127.0.0.1';
  }

  function currentLang(){
    if (isEsHost()) return 'es';
    var path = location.pathname || '/';
    if (path === '/es' || path.indexOf('/es/') === 0) return 'es';
    if ((document.documentElement.lang || '').toLowerCase().indexOf('es') === 0) return 'es';
    return 'en';
  }

  function withSearch(path){
    return path + (location.search || '');
  }

  function enUrl(){
    var p = navPath(location.pathname);
    if (isLocalHost() || !isEsHost()) return withSearch(p);
    return 'https://agentmedicarehub.com' + withSearch(p);
  }

  function esUrl(){
    var p = navPath(location.pathname);
    if (isEsHost()) return withSearch(p);
    if (isLocalHost() && p === '/compliance') return withSearch('/es/compliance');
    if (!isLocalHost() && location.pathname.indexOf('/es/') === 0) return withSearch(location.pathname.replace(/\.html$/i, ''));
    return 'https://es.agentmedicarehub.com' + withSearch(p);
  }

  function insertLangToggle(nav){
    if (nav.querySelector('.lang-toggle')) return;
    var lang = currentLang();
    var wrap = document.createElement('span');
    wrap.className = 'lang-toggle';
    wrap.setAttribute('role', 'group');
    wrap.setAttribute('aria-label', 'Language / Idioma');
    wrap.innerHTML =
      '<a href="' + enUrl() + '" data-set-lang="en"' + (lang === 'en' ? ' class="active" aria-current="true"' : '') + '>EN</a>' +
      '<a href="' + esUrl() + '" data-set-lang="es"' + (lang === 'es' ? ' class="active" aria-current="true"' : '') + '>ES</a>';
    wrap.addEventListener('click', function(e){
      var a = e.target.closest('a[data-set-lang]');
      if (!a) return;
      try { localStorage.setItem('hub_lang', a.getAttribute('data-set-lang')); } catch (err) {}
    });

    var before = null;
    var kids = nav.children;
    var i, el, text, onclick;
    for (i = 0; i < kids.length; i++) {
      el = kids[i];
      text = (el.textContent || '').replace(/\s+/g, ' ').trim();
      onclick = el.getAttribute('onclick') || '';
      if (
        el.tagName === 'BUTTON' ||
        text === '?' ||
        /sign out|cerrar sesi[oó]n/i.test(text) ||
        onclick.indexOf('logout') !== -1 ||
        (el.getAttribute('title') || '').toLowerCase().indexOf('tour') !== -1
      ) {
        before = el;
        break;
      }
    }
    if (before) nav.insertBefore(wrap, before);
    else nav.appendChild(wrap);
  }

  function markActiveNav(nav){
    var path = navPath(location.pathname);
    var links = nav.querySelectorAll('a[href]');
    var i, a, href, h, matched = null;
    for (i = 0; i < links.length; i++) {
      a = links[i];
      if (a.closest('.lang-toggle')) continue;
      href = a.getAttribute('href') || '';
      if (!href || href === '#' || href.indexOf('javascript:') === 0) continue;
      if (/^https?:/i.test(href) || href.charAt(0) === '#') continue;
      h = navPath(href);
      if (h === path) matched = a;
    }
    for (i = 0; i < links.length; i++) {
      if (links[i].closest('.lang-toggle')) continue;
      links[i].classList.remove('active');
    }
    if (matched) matched.classList.add('active');
  }

  function init(){
    var bar = document.querySelector('.top-bar');
    var nav = bar && bar.querySelector('.pill-nav');
    if (!bar || !nav) return;

    nav.id = nav.id || 'hub-pill-nav';
    insertLangToggle(nav);
    markActiveNav(nav);

    if (document.getElementById('hubNavToggle')) return;

    var btn = document.createElement('button');
    btn.type = 'button';
    btn.id = 'hubNavToggle';
    btn.className = 'hub-nav-toggle';
    btn.setAttribute('aria-label', 'Open menu');
    btn.setAttribute('aria-expanded', 'false');
    btn.setAttribute('aria-controls', nav.id);
    btn.innerHTML = '<span class="hub-nav-toggle-bars" aria-hidden="true"><span></span><span></span><span></span></span>';

    bar.insertBefore(btn, nav);

    var overlay = document.createElement('div');
    overlay.className = 'hub-nav-overlay';
    overlay.id = 'hubNavOverlay';
    document.body.appendChild(overlay);

    document.documentElement.classList.add('hub-nav-ready');
    document.body.classList.add('hub-nav-ready');

    function isMobile(){
      return window.matchMedia(MQ).matches;
    }

    function close(){
      document.body.classList.remove('hub-nav-open');
      btn.setAttribute('aria-expanded', 'false');
      btn.setAttribute('aria-label', 'Open menu');
      document.documentElement.classList.remove('hub-nav-open');
    }

    function open(){
      document.body.classList.add('hub-nav-open');
      document.documentElement.classList.add('hub-nav-open');
      btn.setAttribute('aria-expanded', 'true');
      btn.setAttribute('aria-label', 'Close menu');
    }

    function toggle(){
      if (document.body.classList.contains('hub-nav-open')) close();
      else open();
    }

    btn.addEventListener('click', toggle);
    overlay.addEventListener('click', close);
    nav.addEventListener('click', function(e){
      if (!isMobile()) return;
      if (e.target.closest('a,button')) close();
    });
    document.addEventListener('keydown', function(e){
      if (e.key === 'Escape') close();
    });
    window.addEventListener('resize', function(){
      if (!isMobile()) close();
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();

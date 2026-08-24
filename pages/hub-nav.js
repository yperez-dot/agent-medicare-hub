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

  function markActiveNav(nav){
    var path = navPath(location.pathname);
    var links = nav.querySelectorAll('a[href]');
    var i, a, href, h, matched = null;
    for (i = 0; i < links.length; i++) {
      a = links[i];
      href = a.getAttribute('href') || '';
      if (!href || href === '#' || href.indexOf('javascript:') === 0) continue;
      if (/^https?:/i.test(href) || href.charAt(0) === '#') continue;
      h = navPath(href);
      if (h === path) matched = a;
    }
    for (i = 0; i < links.length; i++) {
      links[i].classList.remove('active');
    }
    if (matched) matched.classList.add('active');
  }

  function init(){
    var bar = document.querySelector('.top-bar');
    var nav = bar && bar.querySelector('.pill-nav');
    if (!bar || !nav) return;

    nav.id = nav.id || 'hub-pill-nav';
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

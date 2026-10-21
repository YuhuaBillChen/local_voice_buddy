// Host bridge for Buddy's sandboxed srcdoc answers. Never grants same-origin access.
(() => {
  const isBuddy = f => f.getAttribute('srcdoc')?.includes('data-buddy-answer');
  function theme(frame) {
    frame.contentWindow?.postMessage({type:'buddy:theme',dark:document.documentElement.classList.contains('dark') || document.documentElement.classList.contains('oled-dark')}, '*');
  }
  window.buddyPrepare = function(source) {
    if (!source?.includes('data-buddy-template')) return source;
    const doc = new DOMParser().parseFromString(source, 'text/html');
    const template = doc.querySelector('template[data-buddy-template]');
    if (!template) return source;
    const body = template.content;
    const config = body.querySelector('#buddy-config');
    if (!config) return source;
    const data = JSON.parse(config.textContent);
    data.origin = location.origin;
    config.textContent = JSON.stringify(data).replaceAll('<','\\u003c').replaceAll('>','\\u003e').replaceAll('&','\\u0026');
    for (const el of body.querySelectorAll('[src],[href]')) {
      for (const attr of ['src','href']) {
        const value = el.getAttribute(attr);
        if (value?.startsWith('https://buddy.invalid/')) el.setAttribute(attr, location.origin + value.slice('https://buddy.invalid'.length));
      }
    }
    const csp = body.querySelector('meta[http-equiv="Content-Security-Policy"]');
    csp.content = csp.content.replaceAll('https://buddy.invalid', location.origin);
    return '<!doctype html><html data-buddy-answer>' + template.innerHTML + '</html>';
  }
  new MutationObserver(() => document.querySelectorAll('iframe').forEach(f => {if(isBuddy(f))theme(f);})).observe(document.documentElement,{attributes:true,attributeFilter:['class']});
  addEventListener('message',event => {
    if(event.data?.type !== 'buddy:ready')return;
    const frame = [...document.querySelectorAll('iframe')].find(f => isBuddy(f) && f.contentWindow === event.source);
    if(frame)theme(frame);
  });
})();

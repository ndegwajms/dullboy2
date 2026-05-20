import type { Page } from "playwright";

const INIT_SCRIPT = `(() => {
  const root = (window.__EXTRACTOR__ = window.__EXTRACTOR__ || {
    requests: [], responses: [], streams: [], manifests: [], blobs: [], json: [], iframes: [], chunks: [], mediaSources: [], diagnostics: []
  });
  const push = (k, v) => { try { root[k].push(v); } catch {} };

  const oldFetch = window.fetch;
  window.fetch = async (...args) => {
    const url = String(args?.[0] ?? '');
    push('requests', { type: 'fetch', url, t: Date.now() });
    const res = await oldFetch(...args);
    push('responses', { url: res.url, status: res.status, ct: res.headers.get('content-type') || '' });
    return res;
  };

  const oldOpen = XMLHttpRequest.prototype.open;
  XMLHttpRequest.prototype.open = function(method, url, ...rest) {
    this.__extractor_url = String(url);
    push('requests', { type: 'xhr', method, url: String(url), t: Date.now() });
    return oldOpen.call(this, method, url, ...rest);
  };

  const oldParse = JSON.parse;
  JSON.parse = function(text, reviver){
    const out = oldParse(text, reviver);
    if (typeof text === 'string' && /(m3u8|mpd|playlist|source|stream|iframe)/i.test(text)) push('json', { text: text.slice(0, 2000) });
    return out;
  };

  const oldRespJson = Response.prototype.json;
  Response.prototype.json = async function() {
    const out = await oldRespJson.call(this);
    try { const str = JSON.stringify(out); if (/(m3u8|mpd|playlist|source|stream|iframe)/i.test(str)) push('json', { url: this.url, payload: str.slice(0, 2000) }); } catch {}
    return out;
  };

  const oldCreateObjectUrl = URL.createObjectURL;
  URL.createObjectURL = function(obj){ const blob = oldCreateObjectUrl.call(this, obj); push('blobs', { blob, type: obj?.type || '' }); return blob; };

  const OldMS = window.MediaSource;
  if (OldMS) {
    window.MediaSource = class extends OldMS {
      constructor(...a){ super(...a); push('mediaSources', { kind: 'MediaSource-created', t: Date.now() }); }
      addSourceBuffer(mime){ push('mediaSources', { kind: 'addSourceBuffer', mime }); return super.addSourceBuffer(mime); }
    }
  }

  const oldAppend = SourceBuffer?.prototype?.appendBuffer;
  if (oldAppend) {
    SourceBuffer.prototype.appendBuffer = function(buf){ push('mediaSources', { kind: 'appendBuffer', size: buf?.byteLength || 0 }); return oldAppend.call(this, buf); }
  }

  const obs = new MutationObserver((list) => {
    for (const m of list) {
      for (const n of m.addedNodes) {
        if (n && n.tagName === 'IFRAME') push('iframes', { src: n.src || '', t: Date.now() });
        if (n && n.tagName === 'SCRIPT' && n.src) push('chunks', n.src);
      }
    }
  });
  obs.observe(document.documentElement || document, { childList: true, subtree: true });
})();`;

export class RuntimeInterceptor {
  static async install(page: Page): Promise<void> {
    await page.addInitScript({ content: INIT_SCRIPT });
  }
}

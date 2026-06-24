let _routes = {};
let _calls = [];
let _origFetch;

export function installFetch(routes) {
  _routes = routes || {};
  _calls = [];
  _origFetch = globalThis.fetch;
  globalThis.fetch = async (url) => {
    _calls.push(url);
    for (const [substr, result] of Object.entries(_routes)) {
      if (url.includes(substr)) {
        if (result instanceof Error) throw result;
        const payload = result.payload;
        return {
          ok: result.ok,
          status: result.status,
          json: async () => payload,
          text: async () => JSON.stringify(payload),
          clone() { return this; },
        };
      }
    }
    throw new Error(`No route for ${url}`);
  };
}

export function restoreFetch() {
  globalThis.fetch = _origFetch;
  _origFetch = undefined;
  _routes = {};
  _calls = [];
}

export function lastCalls() {
  return [..._calls];
}

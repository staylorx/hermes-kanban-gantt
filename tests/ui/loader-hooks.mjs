const HERE = new URL('.', import.meta.url)
const STUB_URLS = {
  '@hermes/plugin-sdk': new URL('./.stubs/sdk.mjs', HERE).href,
  react: new URL('./.stubs/react.mjs', HERE).href,
  'react/jsx-runtime': new URL('./.stubs/jsx-runtime.mjs', HERE).href
}
export function resolve(specifier, context, nextResolve) {
  if (STUB_URLS[specifier]) {
    return { url: STUB_URLS[specifier], shortCircuit: true }
  }
  return nextResolve(specifier, context)
}

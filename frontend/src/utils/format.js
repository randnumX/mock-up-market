/** ₹1,234.56 - never "₹-1,234.56"; the sign, if any, goes before the symbol. */
export function fmtINR(n, opts) {
  return `₹${Math.abs(n).toLocaleString('en-IN', { maximumFractionDigits: 2, ...opts })}`
}

/** Explicit +/- sign before the ₹ symbol: "+₹1,234.56" / "-₹1,234.56" / "₹0.00" */
export function signedINR(n, opts) {
  return `${n < 0 ? '-' : n > 0 ? '+' : ''}${fmtINR(n, opts)}`
}

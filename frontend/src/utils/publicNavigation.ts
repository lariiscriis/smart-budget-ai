// Hash navigation keeps existing Vite deployments working without server rewrites.
export function screenFromHash(hash: string): 'landing' | 'access' | 'app' {
  if (!hash || hash === '#' || hash === '#inicio') return 'landing'
  if (hash === '#login') return 'access'
  return 'app'
}

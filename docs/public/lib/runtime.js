// Cluster Buster animation runtime — shared helpers for every animation page.
// Import as ESM:  import { mount, NS, mk, anim } from '../lib/runtime.js'
//
// Animations follow the D-DET cycle pattern:
//   - mount the spiral icon into a container
//   - run reveal logic against arm groups + individual paths
//   - call ctx.finish(holdMs) when done; runtime auto-replays
import { SVG_MARKUP, ARMS, ARM_COLORS } from './icon.js'

export const NS = 'http://www.w3.org/2000/svg'
export { ARMS, ARM_COLORS }

export function mk(tag, attrs = {}) {
  const el = document.createElementNS(NS, tag)
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, String(v))
  return el
}

// Inject the icon SVG into a container and return arm/path handles.
// Returns: { svg, arms: [{el, paths, color, name, index}], paths: [allPathEls] }
export function mount(container) {
  container.innerHTML = SVG_MARKUP
  const svg = container.querySelector('svg')
  const arms = ARMS.map(meta => {
    const el = svg.querySelector(`#arm-${meta.index}`)
    const paths = Array.from(el.querySelectorAll('path'))
    return { ...meta, el, paths }
  })
  const paths = arms.flatMap(a => a.paths)
  return { svg, arms, paths }
}

export function hideAll(els) { els.forEach(e => { e.style.transition = ''; e.style.opacity = '0' }) }
export function showAll(els) { els.forEach(e => { e.style.transition = ''; e.style.opacity = '1' }) }
export function fadeIn(el, ms = 400, delay = 0) {
  el.style.transition = `opacity ${ms}ms ease ${delay}ms`
  el.style.opacity = '1'
}

// Path's bounding box in viewBox coordinates. SVG `getBBox()` returns the box
// in the element's own local coordinate space — for our paths that ignores the
// per-path `transform="translate(-24.78 -12.74)"` from Illustrator export, so
// the numbers are offset from where the path actually renders. This helper
// applies the path's translate attribute so positions land on the visible art.
const _PATH_TRANSLATE = /translate\(\s*([-\d.]+)[\s,]+([-\d.]+)\s*\)/
export function pathBBox(p) {
  const b = p.getBBox()
  const t = p.getAttribute('transform')
  if (!t) return { x: b.x, y: b.y, width: b.width, height: b.height }
  const m = t.match(_PATH_TRANSLATE)
  if (!m) return { x: b.x, y: b.y, width: b.width, height: b.height }
  return { x: b.x + parseFloat(m[1]), y: b.y + parseFloat(m[2]), width: b.width, height: b.height }
}

// Reveal an entire arm group with a transform-from animation.
// `from` is the starting transform string (e.g. 'rotate(-160deg) scale(0.3)').
// Sets paths to opacity 1 and animates the group's opacity + transform back to identity.
// Returns the total duration so callers can chain `setTimeout(finish, dur)`.
export function groupReveal(arm, { from = 'scale(0)', dur = 700, delay = 0, ease = 'cubic-bezier(.2,1,.3,1)', origin = 'bbox' } = {}) {
  arm.paths.forEach(p => { p.style.cssText = 'opacity:1' })
  let cx, cy
  if (origin === 'bbox') {
    const b = arm.el.getBBox()
    cx = b.x + b.width / 2
    cy = b.y + b.height / 2
  } else if (Array.isArray(origin)) {
    [cx, cy] = origin
  }
  arm.el.style.transformOrigin = `${cx}px ${cy}px`
  arm.el.style.transform = from
  arm.el.style.opacity = '0'
  // Force layout flush so the initial transform/opacity commit BEFORE the transition is armed.
  // Single-rAF deferral is unreliable on iOS Safari — transitions silently skip when the
  // initial state hasn't committed yet.
  void arm.el.getBoundingClientRect()
  arm.el.style.transition = `transform ${dur}ms ${ease} ${delay}ms, opacity ${Math.min(dur, 500)}ms ease ${delay}ms`
  arm.el.style.transform = 'none'
  arm.el.style.opacity = '1'
  return dur + delay
}

// Deterministic PRNG (mulberry32). Packs seed it (e.g. rng(67)) so every
// replay of a cycle is identical — D-DET convention.
export function rng(seed = 1) {
  let a = seed >>> 0
  return () => {
    a = (a + 0x6D2B79F5) >>> 0
    let t = a
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

// The Illustrator export bakes `transform="translate(dx dy)"` onto every path,
// and a CSS `style.transform` OVERRIDES that attribute (SVG2 presentation
// attribute cascade) — naively transforming a path shifts it by +24.78,+12.74.
// Append this as the LAST component of any per-path style transform:
//   p.style.transform = `translate(3px,4px) rotate(10deg)` + bake(p)
export function bake(p) {
  const m = (p.getAttribute('transform') || '').match(_PATH_TRANSLATE)
  return m ? ` translate(${m[1]}px, ${m[2]}px)` : ''
}

// Point at fraction t (0..1) along a path, in viewBox coords (baked translate applied).
export function pathPoint(p, t) {
  const pt = p.getPointAtLength(Math.max(0, Math.min(1, t)) * p.getTotalLength())
  const m = (p.getAttribute('transform') || '').match(_PATH_TRANSLATE)
  return m ? { x: pt.x + parseFloat(m[1]), y: pt.y + parseFloat(m[2]) } : { x: pt.x, y: pt.y }
}

// Center + extent of the rendered icon (union of arm group bboxes — g-level
// getBBox already includes the children's baked translates).
export function iconCenter(arms) {
  let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9
  for (const a of arms) {
    const b = a.el.getBBox()
    x0 = Math.min(x0, b.x); y0 = Math.min(y0, b.y)
    x1 = Math.max(x1, b.x + b.width); y1 = Math.max(y1, b.y + b.height)
  }
  return { cx: (x0 + x1) / 2, cy: (y0 + y1) / 2, x0, y0, x1, y1, w: x1 - x0, h: y1 - y0 }
}

// Expanding shock ring (self-driving, self-removing; data-temp so cycle reset
// also sweeps it). Runs on its own rAF — safe alongside the body's master loop.
export function ring(svg, x, y, { r0 = 2, r1 = 40, ms = 450, color = '#fff', width = 1.5 } = {}) {
  const c = mk('circle', { cx: x, cy: y, r: r0, fill: 'none', stroke: color, 'stroke-width': width, 'data-temp': '' })
  svg.appendChild(c)
  const t0 = performance.now()
  const step = now => {
    const t = Math.min(1, (now - t0) / ms)
    const e = 1 - Math.pow(1 - t, 2.2)
    c.setAttribute('r', String(r0 + (r1 - r0) * e))
    c.setAttribute('opacity', String(1 - t))
    if (t < 1) requestAnimationFrame(step)
    else c.remove()
  }
  requestAnimationFrame(step)
  return c
}

// One-line concept chip, bottom-center of the viewBox — "end by naming the idea".
export function chip(svg, label, { fadeMs = 400, dy = -4, size = 8.5 } = {}) {
  const vb = svg.viewBox.baseVal
  const t = mk('text', {
    x: vb.x + vb.width / 2, y: vb.y + vb.height + dy,
    'text-anchor': 'middle', fill: '#8f8f8f',
    'font-size': String(size), 'letter-spacing': '1.1',
    'font-family': 'system-ui, sans-serif', 'data-temp': '',
  })
  t.textContent = label
  t.style.opacity = '0'
  svg.appendChild(t)
  void t.getBoundingClientRect()
  t.style.transition = `opacity ${fadeMs}ms ease`
  t.style.opacity = '1'
  return t
}

// Lightweight rAF loop with cancel/replay machinery.
//
// `setup({ stage, ... })` runs once and returns a function that schedules the
// reveal cycle. The runner exposes a Replay button that re-fires the cycle.
//
// The cycle should call ctx.finish(holdMs) when its visible state is "done";
// after holdMs, the runtime re-invokes the cycle.
export function anim({ run, hold = 1500, mountSelector = '#stage' }) {
  const stage = document.querySelector(mountSelector)
  const ctx = mount(stage)
  let rAF = 0, timer = 0
  const cancelLoop = () => { if (rAF) cancelAnimationFrame(rAF); rAF = 0 }
  const cancelTimer = () => { if (timer) clearTimeout(timer); timer = 0 }

  ctx.raf = fn => { rAF = requestAnimationFrame(fn) }
  ctx.cancelRaf = cancelLoop
  ctx.finish = (h = hold) => { timer = setTimeout(start, h) }

  function start() {
    cancelLoop(); cancelTimer()
    // Wipe per-cycle inline styles on every targetable element so previous-cycle styles
    // (transform, fill, filter, dasharray, etc.) don't leak into this cycle.
    ctx.paths.forEach(p => { p.style.cssText = 'opacity:0' })
    ctx.arms.forEach(a => { a.el.style.cssText = '' })
    ctx.svg.style.cssText = ''
    // Strip helper layers that animations may have appended.
    ctx.svg.querySelectorAll('[data-temp]').forEach(e => e.remove())
    // Force a layout flush so opacity:0 commits before any transition fires.
    void ctx.svg.getBoundingClientRect()
    run(ctx)
  }

  start()
  return ctx
}

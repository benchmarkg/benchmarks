// site/src/lib/theme.ts -- P2-S2-T07. The three-state theme of 09-design-system.md S9.
//
// The choice is system | light | dark, kept in localStorage under STORAGE_KEY, and system by default:
// "a two-state toggle silently overrides the OS preference forever after one accidental click" (09 S9).
// A choice is written to <html data-theme>, which tokens.css (generated, 09 S9's selectors) reads:
//
//   system   no data-theme attribute: @media (prefers-color-scheme: dark) decides
//   light    data-theme="light", whatever the OS says
//   dark     data-theme="dark", whatever the OS says
//
// PREPAINT is the one render-blocking script the site allows (09 S9, S12.2): Base.astro inlines it first in
// <head>, so the attribute is on <html> before <body> exists and no page ever paints in the wrong theme. It
// repeats apply()'s rule in four lines of ES5 because it runs before any module has loaded; theme.spec.ts
// holds the two to the same behaviour.

export type ThemeChoice = 'system' | 'light' | 'dark';
export type Theme = 'light' | 'dark';

export const STORAGE_KEY = 'uaibi-theme';
export const CHOICES: readonly ThemeChoice[] = ['system', 'light', 'dark'];
export const CHANGE_EVENT = 'uaibi:themechange';
const DARK_QUERY = '(prefers-color-scheme: dark)';

export const PREPAINT = [
  'try { var t = localStorage.getItem("' + STORAGE_KEY + '");',
  '  if (t === "light" || t === "dark") document.documentElement.setAttribute("data-theme", t);',
  '  else document.documentElement.removeAttribute("data-theme");',
  '} catch (e) {}',
].join('\n');

const isChoice = (v: unknown): v is ThemeChoice => typeof v === 'string' && (CHOICES as readonly string[]).includes(v);

/** The stored choice, or system when there is none, it is not one of the three, or storage is refused. */
export function readChoice(storage: Storage | undefined = globalThis.localStorage): ThemeChoice {
  try {
    const v = storage?.getItem(STORAGE_KEY);
    return isChoice(v) ? v : 'system';
  } catch {
    return 'system';
  }
}

/** The theme a choice shows, given whether the OS prefers dark. */
export function resolve(choice: ThemeChoice, prefersDark: boolean): Theme {
  return choice === 'system' ? (prefersDark ? 'dark' : 'light') : choice;
}

export function prefersDark(win: Window = window): boolean {
  return win.matchMedia(DARK_QUERY).matches;
}

/** The theme the page shows now: the data-theme attribute, else the OS preference. */
export function current(doc: Document = document): Theme {
  const attr = doc.documentElement.getAttribute('data-theme');
  return attr === 'light' || attr === 'dark' ? attr : prefersDark(doc.defaultView ?? window) ? 'dark' : 'light';
}

/** Write a choice to <html>: the same rule PREPAINT applies before first paint. */
export function apply(choice: ThemeChoice, doc: Document = document): void {
  if (choice === 'system') doc.documentElement.removeAttribute('data-theme');
  else doc.documentElement.setAttribute('data-theme', choice);
}

/** Store a choice, apply it, and tell listeners the theme it now shows. System is stored as no entry. */
export function setChoice(choice: ThemeChoice, doc: Document = document): Theme {
  try {
    if (choice === 'system') localStorage.removeItem(STORAGE_KEY);
    else localStorage.setItem(STORAGE_KEY, choice);
  } catch {
    // storage refused (private mode, a blocked origin): the choice still holds for this page
  }
  apply(choice, doc);
  const theme = current(doc);
  doc.dispatchEvent(new CustomEvent(CHANGE_EVENT, { detail: { choice, theme } }));
  return theme;
}

/** Call `cb` with the theme shown whenever it changes: a toggle, or the OS preference changing under system.
 *  Returns the unsubscribe function. */
export function onThemeChange(cb: (theme: Theme) => void, doc: Document = document): () => void {
  let last = current(doc);
  const check = () => {
    const now = current(doc);
    if (now !== last) {
      last = now;
      cb(now);
    }
  };
  const mq = (doc.defaultView ?? window).matchMedia(DARK_QUERY);
  mq.addEventListener('change', check);
  doc.addEventListener(CHANGE_EVENT, check);
  return () => {
    mq.removeEventListener('change', check);
    doc.removeEventListener(CHANGE_EVENT, check);
  };
}

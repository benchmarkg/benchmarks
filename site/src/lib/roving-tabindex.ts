// site/src/lib/roving-tabindex.ts -- P2-S5-T03 (09 S8.2 "Atlas", S8.3; 10 V1 "And it is also the legend"). The keys of a
// roving tabindex over a list of clusters, framework-free and as small as it can be: the Atlas route's JavaScript is
// held to 08 S8.1's 120 KB, so this module keeps no state, adds no listener and sets up nothing. The owner
// (islands/Atlas.tsx, over the family index components/AtlasIndex.astro server-renders) gives each cluster's first
// item tabindex 0 and every other item -1 when it takes the list over, and hands the list's keydown events to onKey().
//
// The contract is two attributes: a cluster is an element with `data-roving-group`, an item is a focusable element
// with `data-roving-item` inside one. 09 S8.2's keys, over the linearised node list:
//   Tab, Shift+Tab   the browser's own, between clusters: each cluster holds exactly one item at tabindex 0 -- the one
//                    the arrows last moved to, its first item until then -- so the Tab order is one stop per cluster
//                    and comes back to where the reader left each one
//   Up, Down         within a cluster, to the previous and the next item. The list is vertical, so these are its
//                    arrows; Left, Right, Home and End are left to the browser. They stop at a cluster's ends rather
//                    than wrap or cross into the next cluster, which is Tab's job
//   Enter            the item's own action, left to the browser: a link opens its entry, a button presses
//   Space            on a button, the browser's own press; on any other item `select` (the owner's), the page's scroll
//                    suppressed
//   /                focuses `search()` when it returns a control; with none the key passes. It is a key of the list,
//                    like the others, so it never fires where "/" is typed: no text field is an item
// A key with Alt, Ctrl or Meta held is always the browser's.
//
// step(), the cluster arithmetic, is pure and is what test/atlas.test.mjs checks under Node; the browser half is
// tests/atlas-a11y.spec.ts.

/** Where Up or Down moves from item `at` of the `n` in one cluster, or null for any other key. Never past an end: the
 *  arrows stay inside the cluster. */
export const step = (key: string, at: number, n: number): number | null => (key === 'ArrowDown' ? Math.min(at + 1, n - 1)
  : key === 'ArrowUp' ? Math.max(at - 1, 0) : null);

type Key = Pick<KeyboardEvent, 'key' | 'target' | 'altKey' | 'ctrlKey' | 'metaKey' | 'preventDefault'>;

/** A keydown inside the list: Up, Down, Space and "/" as above; every other key is the browser's. */
export function onKey(e: Key, select: (item: HTMLElement) => void, search: () => HTMLElement | null): void {
  const it = (e.target as Element).closest<HTMLElement>('[data-roving-item]');
  if (!it || e.altKey || e.ctrlKey || e.metaKey) return;
  const all = [...it.closest('[data-roving-group]')!.querySelectorAll<HTMLElement>('[data-roving-item]')];
  const to = all[step(e.key, all.indexOf(it), all.length) ?? -1];
  const s = e.key === '/' && search();
  if (to) {
    for (const x of all) x.tabIndex = x === to ? 0 : -1;
    to.focus();
  } else if (e.key === ' ' && !(it instanceof HTMLButtonElement)) select(it);
  else if (s) s.focus();
  else return;
  e.preventDefault();
}

// site/src/islands/FilterSheet.tsx -- P2-S4-T05 (09 S10 "Browse and search"; 09 S6.2, S6.5, S8.2; 10 V11). The browse
// view at phone width. Below --bp-md the facet rail is a sheet opened from a "Filters (N)" button in a sticky bar above
// the results, the applied filters stay visible as one horizontally scrollable chip row below that button, and the
// result list is the page, which applying a filter never moves. 09 S10 names the failure this exists to avoid: filters
// that are applied but out of sight, so an empty result set reads as "this project has no data" rather than as "you
// have three filters on".
//
// islands/FacetPanel.tsx renders these parts around its own rail and its own chips, so there is one rail, one chip row,
// one selection and one status region at every width. This file adds the sheet and its button, not a second filter
// panel; what is laid out where is pages/benchmarks/index.astro's CSS.
//
// The sheet is the platform's popover (popover="auto", as 09 S6.5 has the provenance popover use), and the button opens
// it through popovertarget, so it works as sent: with JavaScript off the button still opens the sheet, whose rail is
// then the single-facet links the server rendered, and its footer button closes it. From --bp-md up the same element is
// laid out in place as the rail beside the list and the button is not shown. A browser without the Popover API keeps
// the rail stacked above the list, the layout before this task.
//
// What JavaScript adds once the island has hydrated:
//   - the open sheet is modal: everything outside it is inert, and focus moves into it; closing it (its footer button,
//     Escape, or a tap on the scrim above the panel) returns focus to the button, as the platform does for a popover
//     and this file does when a tap on the scrim has let go of focus first
//   - the footer button says how many benchmarks the selection holds
//   - leaving the phone layout with the sheet open closes it, so the rail is back beside the list
//   - usePinnedList(): at phone width a filter applied from the sheet or the chip row keeps the result list where it
//     was on screen. Nothing above the list changes height when a filter changes (the bar and the chip row are one line
//     each, whatever they hold), so in practice the page's scroll position is simply left alone; the pin is what holds
//     the list still when something above it does change, such as the "ignored filter" notice, which a first change
//     clears. Scroll anchoring is off over the panel at phone width (index.astro): left on, Chromium re-anchors the page
//     on a row the filter has moved within the list, and the page jumps (to the top, in tests/browse-mobile.spec.ts's
//     case, with the pin taken out). The one movement left is the browser's own: a filter that shortens
//     the page below the reader's position ends the page higher up.
//
// The page under the open sheet does not scroll: the sheet is its own scroll container, always a pixel taller than the
// screen, with overscroll-behavior: contain, so a drag on the panel or on the scrim scrolls the sheet and stops there.
import { useEffect, useLayoutEffect, useRef, type MouseEvent, type ReactNode, type RefObject } from 'react';

/** The phone layout: below --bp-md, 51rem (09 S5.3). The media queries in pages/benchmarks/index.astro say the same,
 *  since a custom property cannot sit in a media query. */
export const PHONE = '(max-width: 50.99rem)';

/** Make every element outside `el` inert, up to <body>, and return what undoes it. The sheet is a popover, which the
 *  platform does not make modal, and it covers the page, so what is under it must not take focus or a tap. */
function inertOutside(el: Element): () => void {
  const made: HTMLElement[] = [];
  for (let n: Element = el; n.parentElement != null; n = n.parentElement) {
    for (const s of n.parentElement.children) {
      if (s !== n && s instanceof HTMLElement && !s.inert) {
        s.inert = true;
        made.push(s);
      }
    }
    if (n.parentElement === document.body) break;
  }
  return () => {
    for (const s of made) s.inert = false;
  };
}

interface ButtonProps {
  sheet: string;      // the sheet's id
  applied: number;    // how many filters are applied: one per chip
}

/** The bar's button: "Filters (N)", N the chips in the row below it. Shown below --bp-md only. */
export function FilterButton({ sheet, applied }: ButtonProps) {
  return <button type="button" className="open-sheet" popoverTarget={sheet} data-open-sheet>Filters ({applied})</button>;
}

interface SheetProps {
  id: string;
  total: number | null;   // the benchmarks the selection holds, once facets.json is read; null before
  children: ReactNode;    // FacetPanel's rail
}

/** The rail's sheet: a popover below --bp-md, and the rail's place in the grid from --bp-md up. */
export default function FilterSheet({ id, total, children }: SheetProps) {
  const sheet = useRef<HTMLDivElement>(null);
  const panel = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = sheet.current;
    if (el == null) return;
    let restore: (() => void) | null = null;
    let opener: HTMLElement | null = null;
    // beforetoggle runs before the platform moves focus back to the button on close, so the button is no longer inert
    const before = (e: Event) => {
      restore?.();
      restore = null;
      if ((e as ToggleEvent).newState === 'open') {
        opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
        restore = inertOutside(el);
      }
    };
    // on open, the sheet at rest (its scrim showing) and focus in it; on close the platform returns focus to the button,
    // except when nothing in the sheet held it (a tap on the scrim lets go of focus first), and then this does
    const after = (e: Event) => {
      if ((e as ToggleEvent).newState === 'open') {
        el.scrollTop = 0;
        panel.current?.focus({ preventScroll: true });
      } else if (opener != null && (document.activeElement == null || document.activeElement === document.body)) {
        opener.focus({ preventScroll: true });
      }
    };
    const phone = window.matchMedia(PHONE);
    const widened = () => {
      if (!phone.matches && el.matches(':popover-open')) el.hidePopover();
    };
    el.addEventListener('beforetoggle', before);
    el.addEventListener('toggle', after);
    phone.addEventListener('change', widened);
    return () => {
      el.removeEventListener('beforetoggle', before);
      el.removeEventListener('toggle', after);
      phone.removeEventListener('change', widened);
      restore?.();
    };
  }, []);

  // the scrim is the sheet's own box above the panel: a tap there closes the sheet
  const onScrim = (e: MouseEvent<HTMLDivElement>) => {
    if (e.target === e.currentTarget) e.currentTarget.hidePopover();
  };
  const done = total == null
    ? 'Close'
    : total === 0 ? 'Close: no benchmark matches' : `Show ${total} ${total === 1 ? 'benchmark' : 'benchmarks'}`;

  return (
    <div id={id} className="filter-sheet" popover="auto" ref={sheet} onClick={onScrim}>
      <div className="sheet-panel" ref={panel} tabIndex={-1}>
        {children}
        <div className="sheet-foot">
          <button type="button" className="sheet-done" popoverTarget={id} popoverTargetAction="hide">{done}</button>
        </div>
      </div>
    </div>
  );
}

/** Hold `list` still on screen across a filter change at phone width: call the returned function just before applying
 *  one, and after the change renders, the page is scrolled by however far the list moved, which is nothing unless
 *  something above it changed height. From --bp-md up it does nothing, because there the rail scrolls with the page
 *  beside the list, and scrolling the page would move the checkbox under the pointer. */
export function usePinnedList(list: RefObject<HTMLElement | null>): () => void {
  const at = useRef<number | null>(null);
  useLayoutEffect(() => {
    const was = at.current;
    at.current = null;
    if (was == null || list.current == null) return;
    const moved = list.current.getBoundingClientRect().top - was;
    if (moved !== 0) window.scrollBy({ top: moved, behavior: 'instant' });
  });
  return () => {
    at.current = list.current != null && window.matchMedia(PHONE).matches ? list.current.getBoundingClientRect().top : null;
  };
}

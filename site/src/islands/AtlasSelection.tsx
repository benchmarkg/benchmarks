// site/src/islands/AtlasSelection.tsx -- P2-S5-T04 (09 S8.1 "2.5.7 Dragging Movements", S8.2; 10 V1 "Lasso-select").
// The Atlas's selection: a set of benchmarks picked off the map, which a later view takes as a group (10 V1: "send the
// selection to the Comparison Workbench (V5) or the Suite Builder (V10)"). islands/Atlas.tsx owns it and renders these
// parts, as islands/FacetPanel.tsx renders islands/FilterSheet.tsx's: the toolbar above the map, and the lasso over it.
//
// SC 2.5.7 is why the order of the ways in matters. "The Atlas lasso-select must have a non-drag equivalent", and 09
// S8.1 decides which: "the *filter* is the primary selection mechanism ('select all N currently visible'), with
// per-node 'add to selection' via keyboard or click; lasso is a shortcut, never the only path." So:
//   Select all N visible   the primary way. N is what the filter leaves in ink (every node when it applies none), the
//                          filter being the filter bar, a family's Highlight in the index, or a link; pressing it adds
//                          those N to the selection, so a selection can be built over several filters. A button: a
//                          keyboard, a click and a switch all press it, and no drag is involved
//   per node               Space on a benchmark in the family index adds it, or takes it out again (09 S8.2: "Space
//                          toggles selection"), and shows its summary beside the map, as before; a click on its node
//                          opens that summary, whose "Add to selection" (or "Remove from selection") is the click path
//   Clear selection        empties it
//   Lasso                  a toggle, off until pressed. While it is on, a canvas over the map takes the pointer, so a
//                          drag draws a path instead of panning the camera, and on release the nodes inside the path
//                          that the filter leaves in ink join the selection (10 V1: "a canvas overlay plus a
//                          point-in-polygon test against graphToViewport coordinates"). The test is the canvas's own
//                          isPointInPath over the path it drew, at each node's sigma graphToViewport position, which
//                          costs the route less than shipping one. Pressed again, or Escape, and the map pans again
// Nothing here moves a node or the camera: a selection is paint (a ring around each selected node on the map, a check
// after its name in the index) and this toolbar's count, and the page's one status region says the new count, politely
// (09 S8.4). tests/atlas-selection.spec.ts completes a selection with the keyboard alone, pointer events blocked and the
// lasso off.
//
// The selection is `ids`: benchmark ids (an atlas.json node's id is its benchmark's), each once, in the order they were
// added. The toolbar carries the same list, space-separated, as data-atlas-selection, so it can be read from outside
// the island. That is the seam P6-S4-T01 builds on: its add-from-lasso is a control here that hands `ids` to the V10
// basket at /suite/. This task builds neither the basket nor a link to it.
//
// The route's JavaScript is held to 08 S8.1's 120 KB, and every byte of this file counts in it: it is imported
// statically, into the Atlas island's own chunk, and scripts/route_js.mjs counts that chunk and everything it imports.
// Loading it lazily would not take it out of the count (route_js.mjs follows a literal import() too, as 10 means it
// to: everything the route can load) and would add a chunk's overhead, so it is not. It is plain buttons, one canvas
// and no state of its own beyond the path being drawn.
import { useRef, type PointerEvent } from 'react';

/** A point in the map's viewport pixels, where sigma's graphToViewport puts a node. */
export interface Point { x: number; y: number }

interface Props {
  ids: string[];                    // the selection, in the order it was made
  visible: string[];                // the benchmarks the filter leaves in ink: every node when it applies none
  set: (ids: string[]) => void;     // the island's: replace the selection, each id once in the order given
  lasso: boolean;
  setLasso: (on: boolean) => void;
}

/** The toolbar: the count, the primary way in, the way out, and the lasso's toggle. No button here is ever disabled,
 *  so pressing one never drops the keyboard's focus to the page; one with nothing to do does nothing. */
export default function AtlasSelection({ ids, visible, set, lasso, setLasso }: Props) {
  return (
    <div className="selection" role="group" aria-label="Selection" data-atlas-selection={ids.join(' ')}>
      <p className="count">{ids.length} selected</p>
      <button type="button" onClick={() => set([...ids, ...visible])}>Select all {visible.length} visible</button>
      <button type="button" onClick={() => set([])}>Clear selection</button>
      <button type="button" aria-pressed={lasso} onClick={() => setLasso(!lasso)}>Lasso</button>
    </div>
  );
}

/** The lasso: a canvas over the map, mounted while the toggle is on, one CSS pixel to a canvas pixel, so its pixels are
 *  the map's viewport pixels (both fill the stage). A drag draws its path in `ink`. On release the path is closed and
 *  `pick` is handed the point-in-polygon test against it: the canvas's own isPointInPath, which closes an open path
 *  and counts a point inside by the non-zero winding rule, so a loop drawn twice round is still inside. */
export function Lasso({ ink, pick }: { ink: string; pick: (inside: (p: Point) => boolean) => void }) {
  const path = useRef<Point[] | null>(null);
  const on = (e: PointerEvent<HTMLCanvasElement>) => {
    const c = e.currentTarget, g = c.getContext('2d')!;
    if (e.type === 'pointerdown') {
      c.setPointerCapture(e.pointerId);
      path.current = [];
    }
    const p = path.current;
    if (p == null) return;
    p.push({ x: e.nativeEvent.offsetX, y: e.nativeEvent.offsetY });
    c.width = c.clientWidth;               // which clears the canvas, its path and its state
    c.height = c.clientHeight;
    for (const q of p) g.lineTo(q.x, q.y);
    if (e.type === 'pointerup') {
      pick((q) => g.isPointInPath(q.x, q.y));
      path.current = null;
    } else {
      g.strokeStyle = ink;
      g.stroke();
    }
  };
  return <canvas className="lasso" aria-hidden="true" onPointerDown={on} onPointerMove={on} onPointerUp={on} />;
}

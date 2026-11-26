// /feed/corrections.xml -- P3-S10-T09 (10 V8: "a separate corrections feed at /feed/corrections.xml", "a deliberate
// trust instrument, not a technicality"; 05 S8). An RSS 2.0 document of what /corrections/ lists: every published
// correction (tools/build/feed.py's `correction` events, substantive changes only) and every dispute record, each
// item linking its anchor on that page. A dispute's guid carries its status, so its resolution reaches a subscriber as
// a new item rather than as a quiet edit of the old one. lib/corrections.ts has the rules and the serialiser.
//
// Until P3-S10-T09 this URL was an Atom document of the corrections alone, from feed/[name].xml.ts; that route no
// longer emits it, so the two can never collide. A fixed narrative route: it renders in every build (08 S3.4).
import type { APIRoute } from 'astro';
import { corrections, disputes, feedItems, organisationNames, rss } from '../../lib/corrections';
import { corpus } from '../../lib/corpus';

export const GET: APIRoute = () => {
  const records = disputes();
  const items = feedItems(corrections(undefined, records), records, organisationNames(corpus().organization));
  return new Response(rss(items), { headers: { 'Content-Type': 'application/rss+xml; charset=utf-8' } });
};

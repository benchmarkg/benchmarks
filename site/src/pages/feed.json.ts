// /feed.json -- the default feed as JSON Feed 1.1 (V8 "Formats"); same events as /feed.xml.
import type { APIRoute } from 'astro';
import { defaultEvents, jsonFeed } from '../lib/feed';

export const GET: APIRoute = () =>
  new Response(jsonFeed('Benchmark index: releases and changes', defaultEvents()), {
    headers: { 'Content-Type': 'application/feed+json; charset=utf-8' },
  });

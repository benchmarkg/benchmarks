// /feed.xml -- the default Atom feed (V8 "Formats"): every event except the machine-ingested.
import type { APIRoute } from 'astro';
import { atom, atomResponse, defaultEvents } from '../lib/feed';

export const GET: APIRoute = () =>
  atomResponse(atom('default', 'Benchmark index: releases and changes', '/feed.xml', defaultEvents()));

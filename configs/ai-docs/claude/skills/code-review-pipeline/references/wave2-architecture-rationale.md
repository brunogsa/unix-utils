# Why Wave 2 fans out into isolated specialist contexts

Wave 2 fans its eight specialists out as concurrent `review-specialist` agents, one rubric each.

Serial passes shared one warm cache but grew one context: measured runs sat at ~100k resident tokens median and 157k at p90, re-reading all of it every turn.

Eight isolated contexts each carry one rubric instead of eight, and that read saving is what pays for the eight base-context writes the fan-out adds.

Dedup moved to Wave 3 along with it — a specialist that cannot see its siblings cannot skip what they raised.

# cnki_rewrite_sampled_v1

Sample-derived CNKI rewrite package.

This package was distilled from 3 pairs of before/after polishing drafts under:

- `C:\Users\m\Desktop\学术润色`

It does not blindly imitate every raw sample change.
It keeps the stable rewrite direction:

- decompress overly compact academic phrasing
- expose logic more explicitly
- convert nominal stacks into verb-led clauses
- keep tone academic instead of colloquial

Upload target:

- platform: `cnki`
- function_type: `rewrite`

Return fields:

- `text`
- `original_aigc_score`
- `rewritten_aigc_score`
- `algorithm`
- `profile`
- `style_profile`
- `transformation_count`
- `rules_applied`

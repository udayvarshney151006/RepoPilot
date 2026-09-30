# Tiny Shop — RepoPilot demo repository

This small Python shop contains a readable password/JWT login flow, protected
checkout handlers, and JavaScript/TypeScript client helpers. It is teaching code,
not a deployable commerce or authentication service.

The deliberate checkout regression is in `shop/checkout.py`: `calculate_total`
uses `item['quantity']` even though quantity is optional. The test
`test_missing_quantity_defaults_to_one` expects `12.5` for `[{"price": 12.5}]`
and raises `KeyError` before repair. The minimal proposal uses
`item.get('quantity', 1)`; a user must approve it before RepoPilot applies it
to its managed repository copy.

Questions to try:

- Where is password authentication implemented?
- Where is JWT validation happening?
- Explain the complete login flow.
- How does checkout calculate its total?
- What files may be affected if `shop/auth.py` changes?

Agent task: **POST /checkout returns 500 when an item omits quantity. Find the
cause and propose a tested fix.** Docker sandbox test results are real when
execution is available; otherwise RepoPilot displays unavailable.

Developer-only reproduction for this trusted bundled source:

```sh
python -m pip install pytest
python -m pytest -q
```

The baseline suite intentionally includes one failing test. RepoPilot does not
execute arbitrary uploaded repository code directly on the application host.

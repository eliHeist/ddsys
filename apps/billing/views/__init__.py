"""Async views. Reads come from `billing.selectors` (async ORM); every write goes through a service in
`billing.services`, which runs as one transaction. Views only parse forms and render."""

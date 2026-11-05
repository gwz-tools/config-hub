# Extended manual-review DIRECT domain list

The file `review-direct-extended-20261105.txt` preserves the **192-domain historical union** compiled from Dunay/Zorik lists, operator-confirmed DIRECT overrides, and earlier proposed candidate lists.

- **155** explicitly confirmed DIRECT domains (currently live in published `routing-feed/direct.txt`).
- **37** more candidate domains held for human review, including `gorzdrav.spb.ru` and `zdrav.spb.ru` observed on Zorik.
- The extra 37 are **not automatically applied** to the distributed DIRECT rules. A domain being Russian-owned or historically on one router is insufficient to override an explicit user policy on all clients.
- Add a reviewed domain to `routing/confirmed-direct-20261105.txt`, open PR, pass conflict tests, then merge. The feed publisher updates it automatically.
- To remove, delete the corresponding line from the confirmed file; tests and content-hash versioning work without fixed domain counts.

**Do not point automatic Podkop or app importers at the extended review file.** Only the published `routing-feed/direct.txt` is the approved canonical DIRECT policy.

The current published domain list is here: https://raw.githubusercontent.com/gwz-tools/config-hub/routing-feed/direct.txt

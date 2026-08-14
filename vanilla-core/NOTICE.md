# Notice

Vanilla Core
Copyright (c) 2026 Shibbieness (Mark) · M MAOU LLC

## Authorship and affiliation

Authored by Shibbieness with AI assistance (Claude). Vanilla Core is an
independent project and is not affiliated with or endorsed by
any AI vendor — the tooling is incidental, the way a compiler or an IDE is.

Practical consequence: commits, files, and docs here carry the maintainer's
name, not a vendor's. No vendor email addresses in author fields, no vendor
co-author trailers, no links back to private chat sessions.
`vanilla_core.floor.check_floor` enforces that for flavor manifests so it
can't quietly regress; it does not scan arbitrary commit history, which
stays a per-repository CI concern.

## Attribution requirement

Vanilla Core carries a modest attribution requirement under AGPL-3.0 §7(b).
See `ATTRIBUTION.md` — short version: keep the credit line where users can
find it. Commercial licensees have a separate, larger credit obligation
described in `LICENSE-COMMERCIAL.md`.

## License text provenance

`LICENSE` is the GNU Affero General Public License v3.0. It was **not**
typed from memory. Network egress to gnu.org was blocked in the environment
where this repository was assembled, so the file was copied byte-for-byte
out of the `matrix-synapse` source distribution
(`matrix_synapse-1.158.0.tar.gz`, file `LICENSE-AGPL-3.0`, fetched from
PyPI), a widely-mirrored project that ships the canonical text.

As received: 34,523 bytes, 661 lines,
SHA-256 `0d96a4ff68ad6d4b6f1f30f713b18d5184912ba8dd389f86aa7710db079abcb0`.

Verify it against the authoritative source before relying on it:

```
curl -sS https://www.gnu.org/licenses/agpl-3.0.txt | diff - LICENSE
```

If a discrepancy is ever found, the gnu.org text controls and this file
should be corrected immediately.

## Not legal advice

Nothing in this repository — `LICENSE`, `LICENSE-COMMERCIAL.md`,
`ATTRIBUTION.md`, or `STANDARDS.md` — is legal advice, and none of it has
been reviewed by an attorney. It reflects the maintainer's plain-language
intent: free for individuals, students, nonprofits, and small commercial
use; anything built on top stays free under the same terms; a paid
commercial license is available for anyone who wants out of that
obligation. Get an actual lawyer before treating any of it as binding in a
real dispute — especially the commercial terms and the attribution
requirement, which are the two places where a homemade clause is most
likely to cause trouble.

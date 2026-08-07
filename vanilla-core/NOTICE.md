# NOTICE

**Vanilla Core is an independent project. It is not affiliated with, endorsed
by, sponsored by, or acting on behalf of Anthropic, PBC, or any AI vendor.**
Any AI-assisted tooling used to help author this codebase is incidental —
like a compiler or an IDE — and confers no affiliation, partnership, or
authorship claim by that vendor. No commit, file, or piece of documentation
in this repository should carry a vendor email address, vendor co-author
trailer, or a link back to a private chat session. If you find one, it's a
bug — open an issue or just delete it and say why in the commit message.
`vanilla_core.floor.check_floor` enforces this at the flavor-manifest level
so it can't silently regress for anything built on top of Vanilla Core; it
does not (yet) scan arbitrary commit history, which is a manual/CI concern
per repository.

## License text provenance

`LICENSE` in this repository is the GNU Affero General Public License v3.0.
It was **not** typed from memory. Network egress to gnu.org was blocked in
the environment where this repository was assembled, so the file was copied
byte-for-byte out of the `matrix-synapse` source distribution
(`matrix_synapse-1.158.0.tar.gz`, file `LICENSE-AGPL-3.0`, fetched from
PyPI), a widely-mirrored project that ships the canonical text.

As received: 34,523 bytes, 661 lines,
SHA-256 `0d96a4ff68ad6d4b6f1f30f713b18d5184912ba8dd389f86aa7710db079abcb0`.

Verify it yourself against the authoritative source before relying on it:

```
curl -sS https://www.gnu.org/licenses/agpl-3.0.txt | diff - LICENSE
```

If a discrepancy is ever found, the gnu.org text controls, and this file
should be corrected immediately.

## Not legal advice

Nothing in this repository — `LICENSE`, `LICENSE-COMMERCIAL.md`, or
`STANDARDS.md` — is legal advice, and none of it has been reviewed by an
attorney. It reflects the maintainer's plain-language intent (free for
individuals, students, nonprofits, and small commercial use; anything built
on top stays free under the same terms; a paid commercial license is
available for anyone who wants to use the code without the copyleft
obligation). Get an actual lawyer before treating any of this as binding in
a real commercial dispute, especially the commercial-license terms, which
are currently a placeholder.

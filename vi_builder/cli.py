#!/usr/bin/env python3
"""
VI Builder — command-line interface.

Phase 1 gate (spec Section 12): "Connect a local directory, ingest files,
query Registry from the command line. Prompt Capsule and RAG Package
processes visible." This CLI is the whole L7 surface for Phase 1 — the
Cockpit (L7 HTML UI) is Phase 2.

Usage:
    python -m vi_builder.cli sources add --path <dir> [--name NAME] [--type local_path] [--label DEFAULT]
    python -m vi_builder.cli sources list
    python -m vi_builder.cli sources status <source_id>
    python -m vi_builder.cli ingest <source_id>
    python -m vi_builder.cli processes list [--source ID] [--tier 4a] [--staleness FRESH] [--tag TAG]
    python -m vi_builder.cli processes view <process_id>
    python -m vi_builder.cli processes search <query>
    python -m vi_builder.cli watch <source_id> [--iterations N]
"""

import argparse
import sys
from pathlib import Path

from vi_builder.config import resolve_data_dir
from vi_builder.daemon import (
    ArtifactEvent, FilesystemSource, Watcher,
    compute_fingerprint, compare_fingerprints, label_for_conn_type, walk_source,
)
from vi_builder.factory import build_prompt_capsule, build_rag_package
from vi_builder.ingestion import extract, is_tier4_eligible
from vi_builder.registry import Registry


def _get_registry(args) -> Registry:
    data_dir = resolve_data_dir(getattr(args, 'data_dir', None))
    return Registry(data_dir)


def cmd_sources_add(args):
    reg = _get_registry(args)
    try:
        root = Path(args.path).expanduser().resolve()
        if not root.is_dir():
            print(f"error: {root} is not a directory", file=sys.stderr)
            return 1

        existing = reg.find_source_by_path(str(root))
        if existing:
            print(f"already connected: {existing['source_id']} ({existing['name']})")
            return 0

        label = label_for_conn_type(args.type)
        if args.label:
            label = args.label  # explicit override, e.g. forcing OPTIONAL

        name = args.name or root.name
        source_id = reg.connect_source(name, str(root), args.type, label)

        fingerprint = compute_fingerprint(root)
        reg.set_fingerprint(source_id, fingerprint)

        print(f"connected: {source_id}")
        print(f"  name:  {name}")
        print(f"  path:  {root}")
        print(f"  type:  {args.type} ({label})")
        print(f"  fingerprint: {fingerprint['file_count']} files, "
              f"{len(fingerprint['extension_distribution'])} extensions")
        print("FS_CONNECTED")
        return 0
    finally:
        reg.close()


def cmd_sources_list(args):
    reg = _get_registry(args)
    try:
        sources = reg.list_sources()
        if not sources:
            print("(no sources connected)")
            return 0
        for s in sources:
            print(f"{s['source_id']}  [{s['label']:8}] {s['status']:12} {s['name']:20} {s['path']}")
        return 0
    finally:
        reg.close()


def cmd_sources_status(args):
    reg = _get_registry(args)
    try:
        s = reg.get_source(args.source_id)
        if not s:
            print(f"error: no such source {args.source_id}", file=sys.stderr)
            return 1
        print(f"source_id:      {s['source_id']}")
        print(f"name:           {s['name']}")
        print(f"path:           {s['path']}")
        print(f"type:           {s['conn_type']} ({s['label']})")
        print(f"status:         {s['status']}")
        print(f"connected_at:   {s['connected_at']}")
        print(f"last_ingest_at: {s['last_ingest_at']}")
        processes = reg.catalog(source_id=args.source_id)
        print(f"processes:      {len(processes)}")
        return 0
    finally:
        reg.close()


def cmd_ingest(args):
    reg = _get_registry(args)
    try:
        source = reg.get_source(args.source_id)
        if not source:
            print(f"error: no such source {args.source_id}", file=sys.stderr)
            return 1
        if source['status'] != 'connected':
            print(f"error: source {args.source_id} is disconnected", file=sys.stderr)
            return 1

        root = Path(source['path'])
        if not root.is_dir():
            print(f"error: {root} no longer exists")
            reg.disconnect_source(args.source_id)
            print("FS_DISCONNECTED")
            return 1

        files = walk_source(root)
        print(f"scanning {root} — {len(files)} files")

        results = []
        capsule_count = 0
        skipped = 0
        for f in files:
            result = extract(f)
            if not is_tier4_eligible(result):
                skipped += 1
                continue
            results.append(result)

            capsule = build_prompt_capsule(result, root)
            source_hash = None
            from vi_builder.daemon import file_hash
            source_hash = file_hash(f)
            process_id = reg.register_process(
                slug=str(f.relative_to(root)),
                tier='4a',
                format_type=capsule.format_type,
                source_id=args.source_id,
                source_path=str(f),
                source_hash=source_hash,
                content_text=capsule.to_json_text(),
                tags=[result.artifact_type],
            )
            capsule_count += 1

        rag = build_rag_package(results, root, source['name'])
        rag_process_id = reg.register_process(
            slug=f"{source['name']}-rag-package",
            tier='4b',
            format_type=rag.format_type,
            source_id=args.source_id,
            source_path=str(root),
            source_hash=compute_fingerprint(root)['directory_structure_hash'],
            content_text=rag.to_json_text(),
            tags=['aggregate'],
        )

        reg.mark_ingested(args.source_id)
        fingerprint = compute_fingerprint(root)
        reg.set_fingerprint(args.source_id, fingerprint)

        print(f"built {capsule_count} Prompt Capsule processes (Tier 4a)")
        print(f"built 1 RAG Package process (Tier 4b): {rag_process_id} "
              f"({rag.payload['chunk_count']} chunks across {len(rag.payload['files_covered'])} files)")
        print(f"skipped {skipped} files (binary/empty/ineligible)")
        return 0
    finally:
        reg.close()


def cmd_processes_list(args):
    reg = _get_registry(args)
    try:
        records = reg.catalog(
            source_id=args.source, tier=args.tier, format_type=args.format_type,
            staleness=args.staleness, tag=args.tag,
        )
        if not records:
            print("(no processes match)")
            return 0
        for r in records:
            print(f"{r.process_id}  tier={r.tier:3} [{r.staleness_state:9}] {r.format_type:15} {r.slug}")
        return 0
    finally:
        reg.close()


def cmd_processes_view(args):
    reg = _get_registry(args)
    try:
        record = reg.view(args.process_id)
        if not record:
            print(f"error: no such process {args.process_id}", file=sys.stderr)
            return 1
        content = reg.read_content(args.process_id)
        print(f"process_id:      {record.process_id}")
        print(f"slug:            {record.slug}")
        print(f"tier:            {record.tier}")
        print(f"format_type:     {record.format_type}")
        print(f"source_id:       {record.source_id}")
        print(f"source_path:     {record.source_path}")
        print(f"staleness_state: {record.staleness_state}")
        print(f"build_timestamp: {record.build_timestamp}")
        print(f"tags:            {record.tags}")
        print("--- content preview ---")
        print((content or '')[:1000])
        reg.record_usage(args.process_id)
        return 0
    finally:
        reg.close()


def cmd_processes_search(args):
    reg = _get_registry(args)
    try:
        records = reg.search(args.query, limit=args.limit)
        if not records:
            print("(no matches)")
            return 0
        for r in records:
            print(f"{r.process_id}  tier={r.tier:3} {r.format_type:15} {r.slug}")
        return 0
    finally:
        reg.close()


def cmd_watch(args):
    reg = _get_registry(args)
    try:
        source = reg.get_source(args.source_id)
        if not source:
            print(f"error: no such source {args.source_id}", file=sys.stderr)
            return 1
        root = Path(source['path'])
        fs_source = FilesystemSource(args.source_id, root)
        fs_source.diff_since_last_scan()  # baseline snapshot, no events printed
        watcher = Watcher(fs_source, debounce_seconds=args.debounce)

        def on_events(events):
            for e in events:
                print(f"{e.event_type}  {e.path}")

        print(f"watching {root} (debounce={args.debounce}s, {args.iterations} polls)...")
        watcher.run(on_events, poll_interval=args.poll_interval, max_iterations=args.iterations)
        return 0
    finally:
        reg.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog='vi-builder', description='VI Builder Phase 1 CLI')
    parser.add_argument('--data-dir', default=None, help='Override VI Builder data directory')
    sub = parser.add_subparsers(dest='command', required=True)

    sources = sub.add_parser('sources', help='Manage Filesystem Sources (L1)')
    sources_sub = sources.add_subparsers(dest='sources_command', required=True)

    add_p = sources_sub.add_parser('add', help='Connect a local directory as a source')
    add_p.add_argument('--path', required=True)
    add_p.add_argument('--name', default=None)
    add_p.add_argument('--type', default='local_path', choices=['local_path', 'fuse_mount', 'removable', 'ssh', 'smb_nfs'])
    add_p.add_argument('--label', default=None, choices=['DEFAULT', 'OPTIONAL'])
    add_p.set_defaults(func=cmd_sources_add)

    list_p = sources_sub.add_parser('list', help='List connected sources')
    list_p.set_defaults(func=cmd_sources_list)

    status_p = sources_sub.add_parser('status', help='Show a source and its process count')
    status_p.add_argument('source_id')
    status_p.set_defaults(func=cmd_sources_status)

    ingest_p = sub.add_parser('ingest', help='Full ingest of a connected source (L2 + L3 + L4)')
    ingest_p.add_argument('source_id')
    ingest_p.set_defaults(func=cmd_ingest)

    processes = sub.add_parser('processes', help='Query the Process Registry (L4)')
    processes_sub = processes.add_subparsers(dest='processes_command', required=True)

    plist = processes_sub.add_parser('list', help='List processes with filters')
    plist.add_argument('--source', default=None)
    plist.add_argument('--tier', default=None)
    plist.add_argument('--format-type', dest='format_type', default=None)
    plist.add_argument('--staleness', default=None)
    plist.add_argument('--tag', default=None)
    plist.set_defaults(func=cmd_processes_list)

    pview = processes_sub.add_parser('view', help='View full process detail')
    pview.add_argument('process_id')
    pview.set_defaults(func=cmd_processes_view)

    psearch = processes_sub.add_parser('search', help='Full-text search across process content')
    psearch.add_argument('query')
    psearch.add_argument('--limit', type=int, default=20)
    psearch.set_defaults(func=cmd_processes_search)

    watch_p = sub.add_parser('watch', help='Continuously watch a connected source (debounced polling)')
    watch_p.add_argument('source_id')
    watch_p.add_argument('--iterations', type=int, default=10)
    watch_p.add_argument('--poll-interval', type=float, default=1.0)
    watch_p.add_argument('--debounce', type=float, default=2.0)
    watch_p.set_defaults(func=cmd_watch)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except BrokenPipeError:
        # Output piped into something like `head` that closed early.
        sys.exit(0)

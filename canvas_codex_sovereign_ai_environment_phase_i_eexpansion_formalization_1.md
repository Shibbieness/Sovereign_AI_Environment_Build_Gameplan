# Canvas Codex — Sovereign AI Environment Phase I EExpansion & Formalization

---

## I. Purpose

This document EExpands the Phase I Engineering Specification into:

1. Concrete Rust/Go scaffolding architecture
2. RFC-grade formalization of the .saipkg package format
3. Algorithm-level Filesystem Intelligence Engine design
4. Detailed IDE UI wireframe and layout architecture

This transitions the system from structured blueprint to implementation-ready foundation.

---

# PART I — Phase I Executable Scaffolding (Rust Primary, Go Alternative)

---

## 1. Language Selection Rationale

Rust (Preferred):
- Memory safety
- Deterministic performance
- Strong type guarantees
- Concurrency safety
- Ideal for core system + sandboxing

Go (Alternative Core Services):
- Fast development velocity
- Strong concurrency model
- Simple deployment

Hybrid option:
- Rust for core engine
- Go for runtime orchestration services

---

## 2. Rust Workspace Structure

Root:

sovereign/
  Cargo.toml (workspace)
  /crates
    /core
    /runtime
    /filesystem_engine
    /package_engine
    /vault
    /model_registry
    /ide_backend
    /daemon_manager

---

## 3. Crate Responsibilities

### core
- Bootstrap sequence
- Configuration parsing
- Global state registry
- Logging system

### runtime
- Agent execution loop
- Sandbox interface
- Resource quota enforcement

### filesystem_engine
- File scanning
- Classification
- Dependency parsing
- Graph builder

### package_engine
- .saipkg parser
- Signature validation
- Dependency resolver
- Rollback snapshot manager

### vault
- Encrypted key storage
- Permission scoping
- Audit logs

### model_registry
- Model metadata DB
- Install/uninstall handlers
- Routing selector logic

### ide_backend
- IPC layer to frontend
- Graph data API
- Runtime control endpoints

### daemon_manager
- Persistent background processes
- Scheduling
- Auto-restart logic

---

## 4. Core Bootstrap (Rust Pseudocode)

fn main() {
  init_logger();
  load_config();
  validate_storage();
  init_database();
  register_models();
  load_packages();
  start_runtime_manager();
  launch_ide_backend();
}

All steps return Result<T, SovereignError>.

---

# PART II — RFC-Grade Specification for .saipkg

---

## RFC-SAI-0001

Title: Sovereign AI Package Format (.saipkg)
Status: Draft
Version: 1.0

---

## 1. Abstract

The .saipkg format defines a deterministic, signed, dependency-aware package format for the Sovereign AI Environment.

---

## 2. Terminology

Package: Installable extension unit
Manifest: JSON metadata file
Payload: File content
Hook: Controlled executable script
Signature: Cryptographic verification artifact

---

## 3. File Structure

.saipkg MUST be a compressed archive containing:

/manifest.json
/payload/
/hooks/
/signature.sig

---

## 4. Manifest Schema (Normative)

Fields:

name (string, required)
version (string, semver, required)
author (string, required)
description (string)
dependencies (array)
runtime_hooks (array)
required_models (array)
filesystem_rules (object)
permissions (object)

---

## 5. Installation Algorithm

1. Verify signature
2. Validate manifest schema
3. Resolve dependency DAG
4. Detect circular references
5. Display install impact
6. Create rollback snapshot
7. Extract payload
8. Execute declared hooks in sandbox
9. Register package

Failure at any stage MUST abort installation.

---

## 6. Security Requirements

- Packages MUST be signed
- Hooks MUST declare required permissions
- No implicit filesystem root access
- Resource caps enforced during hook execution

---

## 7. Versioning Rules

Semantic Versioning required.

Backward-incompatible changes MUST increment major version.

---

# PART III — Filesystem Intelligence Engine (Algorithm-Level)

---

## 1. High-Level Pipeline

Input: File tree
Output: Structured dependency graph + classification map

Pipeline:

Scan → Classify → Parse → Graph Build → Optimize → Suggest

---

## 2. File Classification Algorithm

For each file F:

1. Extract extension
2. Perform MIME detection
3. Run content fingerprinting
4. Language detection via heuristic scoring
5. Assign type confidence score

Confidence > threshold → classify
Else → mark unknown

---

## 3. Dependency Inference Algorithm

For each source file:

1. Parse AST if language supported
2. Extract import/include statements
3. Normalize module paths
4. Add directed edge in graph

Graph G = (Nodes, Edges)

Nodes = Files
Edges = Dependencies

---

## 4. Orphan Detection

Compute in-degree for each node.

If in-degree == 0 AND not entrypoint → candidate orphan.

Mark but do not auto-delete.

---

## 5. Structural Optimization Heuristic

Score folder structure by:

- Average depth
- Dependency locality
- Cross-folder edge density

If cross-density high → suggest folder merge.
If depth > threshold → suggest flattening.

---

## 6. File Lineage Tracking

Metadata table:

file_id
created_by
modified_by
generation_source
linked_runtime
hash_history

Each modification event appended immutably.

---

## 7. Auto-Organization Algorithm

When new files added:

1. Classify
2. Infer dependencies
3. Compare against existing graph clusters
4. Assign cluster membership
5. Suggest relocation path

Cluster detection via:

- Community detection algorithm (Louvain method)
OR
- Simple modularity clustering (Phase I)

---

# PART IV — IDE UI Wireframe System

---

## 1. Layout Philosophy

Three-column adaptive layout:

Left: Project Explorer + Graph Navigator
Center: Editor + Structural View
Right: Runtime + Model + Vault Panels
Bottom: Console + Logs

---

## 2. Core Views

### A. Project Explorer
- File tree
- Dependency overlay toggle
- Orphan markers

### B. Structural Graph View
- Node-link diagram
- Filter by runtime
- Highlight circular dependencies

### C. Editor Panel
- Split view
- AI suggestion overlay
- Inline dependency highlight

### D. Runtime Dashboard
- Active agents list
- Resource meters
- Model selection dropdown
- Iteration counter

### E. Package Manager View
- Installed packages list
- Dependency graph
- Install impact preview modal

### F. Vault Panel
- Named keys list
- Scope tags
- Access logs

---

## 3. Interaction Model

All state changes:

- Confirmed via modal if structural
- Logged to event stream
- Reversible

Drag-and-drop file relocation triggers:

- Dependency re-evaluation
- Graph update
- Integrity validation

---

## 4. UI State Persistence

UI layout saved as:

/ui_state.json

Includes:
- Open panels
- Graph filters
- Runtime preferences

---

# PART V — Phase I Implementation Milestones

Milestone 1:
- Workspace compiles
- Bootstrap runs
- IDE window opens

Milestone 2:
- File scan + classification works
- Graph builds for small project

Milestone 3:
- .saipkg install + rollback functional

Milestone 4:
- Runtime executes basic agent loop
- Resource caps enforced

---

# PART VI — Structural Stability Guarantees

- Immutable core modules
- All graph changes logged
- Package rollback guaranteed
- Sandboxed runtime enforced

Phase I establishes deterministic sovereignty foundation.

---

End of Codex.


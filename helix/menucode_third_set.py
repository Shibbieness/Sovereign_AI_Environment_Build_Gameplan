# ==================================================
# MENUCODE CUSTOM THIRD SET — RUNTIME SYSTEM
# Vanilla variant (general-purpose, scrubbed)
# ==================================================

"""
==================================================
[ CUSTOM THIRD SET — VANILLA ]
==================================================

Purpose:
Synthesis of MenuCode prototype delineation,
combined annotations, and canonical fragments.

This Vanilla variant contains no project-specific
content. It is suitable for public release,
educational reference, and general distribution.

For project-specific Flavor variants, see the
parallel files in the project's Flavor directory.

Design properties preserved across the synthesis:
- Heavy section delineation (from Codex 2 prototype)
- Triple-quoted docstring annotations (from Codex 2)
- Architectural commentary (from Codex 3)
- Seven canonical fragments (from Codex 3)
- Fragment registry + MainMenu builder (from Codex 3)
- AUTO_ARCHIVE persistence option (from Codex 2)
- Vanilla/Flavor variant discipline (from Helix Codex Stage 10)
==================================================
"""

import json
import time
import os


# ==================================================
# RUNTIME CONTEXT
# ==================================================

"""
==================================================
[ RUNTIME CONTEXT ]
==================================================

CURRENT_PROFILE selects the operational tier.
CONFIG_PATH is where save_config() persists state.
DEPLOYMENT_CONTEXT determines variant routing
(per Helix Codex Stage 10 Section XLVIII).
==================================================
"""

CURRENT_PROFILE = "BALANCED"
CONFIG_PATH = "./runtime_config.json"
DEPLOYMENT_CONTEXT = "public"  # public | internal | specific:{project_id}


# ==================================================
# FRAGMENTS (SEVEN CANONICAL + EXTENSIBLE)
# ==================================================

"""
==================================================
[ FRAGMENT 1 — MODEL_ROUTING ]
==================================================

Purpose:
Routes inference requests among models with
depth and adaptability constraints.

Operational role: structural (the architectural
commitment about what models exist in the
routing structure).

Each option's documentation lives in
MODEL_ROUTING_NOTES below the fragment.
==================================================
"""

MODEL_ROUTING = {
    "PRIMARY_MODEL": "smallthinker:3b",
    "SECONDARY_MODEL": "codellama:7b",
    "FALLBACK_MODEL": "tinyllama:1.1b",
    "ROUTING_MODE": "ADAPTIVE",
    "MAX_ROUTE_DEPTH": 3
}

MODEL_ROUTING_NOTES = {
    "PRIMARY_MODEL": {
        "description": "Primary model identifier; receives most inference requests by default.",
        "type": "string",
        "valid_range": "Any model identifier registered in the local model registry.",
        "default": "smallthinker:3b",
        "semantic_role": "structural",
        "affects": ["MES_OPTIONS", "RAG_OPTIONS", "HARDWARE_PROFILE"],
        "requires": []
    },
    "SECONDARY_MODEL": {
        "description": "Secondary model for tasks the primary cannot handle, or as fallback for routing depth > 1.",
        "type": "string",
        "valid_range": "Same as PRIMARY_MODEL; can be the same value if no secondary is needed.",
        "default": "codellama:7b",
        "semantic_role": "structural",
        "affects": ["MES_OPTIONS", "RAG_OPTIONS"],
        "requires": ["PRIMARY_MODEL"]
    },
    "FALLBACK_MODEL": {
        "description": "Emergency fallback model invoked only if primary and secondary both fail.",
        "type": "string",
        "valid_range": "Lightweight model recommended (e.g., 'tinyllama:1.1b').",
        "default": "tinyllama:1.1b",
        "semantic_role": "structural",
        "affects": ["HARDWARE_PROFILE"],
        "requires": ["PRIMARY_MODEL"]
    },
    "ROUTING_MODE": {
        "description": "Strategy for selecting which model handles each request.",
        "type": "enum",
        "valid_range": "STATIC | ADAPTIVE | LOAD_BALANCED | EXPLICIT",
        "default": "ADAPTIVE",
        "semantic_role": "computational",
        "affects": ["MES_OPTIONS"],
        "requires": []
    },
    "MAX_ROUTE_DEPTH": {
        "description": "Maximum routing hops before falling back. Prevents infinite routing loops.",
        "type": "int",
        "valid_range": "1 to 10; recommended 2-3 for low-RAM systems.",
        "default": 3,
        "semantic_role": "temporal",
        "affects": ["MES_OPTIONS"],
        "requires": []
    }
}


# --------------------------------------------------

"""
==================================================
[ FRAGMENT 2 — MES_OPTIONS ]
==================================================

Purpose:
Time-slices model execution under RAM/CPU
constraints. The Model Execution Scheduler
options.

Operational role: temporal (constrains how
sequential operations happen).
==================================================
"""

MES_OPTIONS = {
    "EXECUTION_SLICE_MS": 100,
    "MAX_CONCURRENT_GRAPHS": 1,
    "CHECKPOINT_INTERVAL": 300,
    "DYNAMIC_THROTTLING": True
}

MES_OPTIONS_NOTES = {
    "EXECUTION_SLICE_MS": {
        "description": "Time slice (ms) per execution step before yielding to scheduler.",
        "type": "int",
        "valid_range": "10 to 1000; recommended 50-200 for interactive workloads.",
        "default": 100,
        "semantic_role": "temporal",
        "affects": ["HARDWARE_PROFILE"],
        "requires": []
    },
    "MAX_CONCURRENT_GRAPHS": {
        "description": "Maximum execution graphs running concurrently.",
        "type": "int",
        "valid_range": "1 to 8; constrained by RAM_LIMIT_GB.",
        "default": 1,
        "semantic_role": "structural",
        "affects": ["HARDWARE_PROFILE"],
        "requires": []
    },
    "CHECKPOINT_INTERVAL": {
        "description": "Seconds between automatic state checkpoints.",
        "type": "int",
        "valid_range": "60 to 3600; lower for high-volatility workloads.",
        "default": 300,
        "semantic_role": "temporal",
        "affects": ["PERSISTENCE_MENU"],
        "requires": []
    },
    "DYNAMIC_THROTTLING": {
        "description": "Enable adaptive throttling under memory/CPU pressure.",
        "type": "bool",
        "valid_range": "True | False",
        "default": True,
        "semantic_role": "computational",
        "affects": ["HARDWARE_PROFILE"],
        "requires": []
    }
}


# --------------------------------------------------

"""
==================================================
[ FRAGMENT 3 — RAG_OPTIONS ]
==================================================

Purpose:
Augments inference with retrieved context
under depth and compression constraints.

Operational role: semantic (context retrieval
shapes inference meaning).
==================================================
"""

RAG_OPTIONS = {
    "RETRIEVAL_DEPTH": 5,
    "VECTOR_DB": "chromadb",
    "CACHE_RETENTION": 100,
    "COMPRESSION_MODE": "MODERATE"
}

RAG_OPTIONS_NOTES = {
    "RETRIEVAL_DEPTH": {
        "description": "Number of context chunks retrieved per inference request.",
        "type": "int",
        "valid_range": "1 to 50; recommended 3-10 for most workloads.",
        "default": 5,
        "semantic_role": "semantic",
        "affects": ["HARDWARE_PROFILE"],
        "requires": []
    },
    "VECTOR_DB": {
        "description": "Vector database backend for similarity search.",
        "type": "enum",
        "valid_range": "chromadb | qdrant | weaviate | sqlite_vss | custom",
        "default": "chromadb",
        "semantic_role": "structural",
        "affects": [],
        "requires": []
    },
    "CACHE_RETENTION": {
        "description": "Number of recent retrievals cached for performance.",
        "type": "int",
        "valid_range": "0 to 1000; 0 disables caching.",
        "default": 100,
        "semantic_role": "temporal",
        "affects": ["HARDWARE_PROFILE"],
        "requires": []
    },
    "COMPRESSION_MODE": {
        "description": "Compression level for cached retrievals.",
        "type": "enum",
        "valid_range": "OFF | LIGHT | MODERATE | AGGRESSIVE",
        "default": "MODERATE",
        "semantic_role": "computational",
        "affects": [],
        "requires": []
    }
}


# --------------------------------------------------

"""
==================================================
[ FRAGMENT 4 — PERSISTENCE_MENU ]
==================================================

Purpose:
Captures runtime state to durable substrate.

Operational role: structural + temporal
(identity-preserving wrapper across time).

AUTO_ARCHIVE field preserved from Codex 2
canonical form (per Section II Alt resolution).
==================================================
"""

PERSISTENCE_MENU = {
    "SAVE_PROFILE": "STANDARD",
    "MAX_REPLAY_HISTORY": 20,
    "ENABLE_GRAPH_COMPRESSION": True,
    "AUTO_ARCHIVE": True
}

PERSISTENCE_MENU_NOTES = {
    "SAVE_PROFILE": {
        "description": "Persistence profile selecting state-capture depth.",
        "type": "enum",
        "valid_range": "MINIMAL | STANDARD | ARCHIVAL",
        "default": "STANDARD",
        "semantic_role": "structural",
        "affects": ["HARDWARE_PROFILE"],
        "requires": []
    },
    "MAX_REPLAY_HISTORY": {
        "description": "Maximum number of historical states retained for replay.",
        "type": "int",
        "valid_range": "0 to 1000; 0 disables replay history.",
        "default": 20,
        "semantic_role": "temporal",
        "affects": ["HARDWARE_PROFILE"],
        "requires": []
    },
    "ENABLE_GRAPH_COMPRESSION": {
        "description": "Compress execution graph state when persisted.",
        "type": "bool",
        "valid_range": "True | False",
        "default": True,
        "semantic_role": "computational",
        "affects": [],
        "requires": []
    },
    "AUTO_ARCHIVE": {
        "description": "Automatically archive old persisted states beyond MAX_REPLAY_HISTORY.",
        "type": "bool",
        "valid_range": "True | False",
        "default": True,
        "semantic_role": "temporal",
        "affects": [],
        "requires": ["MAX_REPLAY_HISTORY"]
    }
}


# --------------------------------------------------

"""
==================================================
[ FRAGMENT 5 — HARDWARE_PROFILE ]
==================================================

Purpose:
Enforces hardware constraint envelope.

Operational role: structural (architectural
commitment about what resources are available).

Validates execution feasibility before any
other Rune fires.
==================================================
"""

HARDWARE_PROFILE = {
    "RAM_LIMIT_GB": 2,
    "ENABLE_SWAP": True,
    "CPU_PRIORITY_MODE": "BALANCED",
    "GPU_ACCELERATION": False
}

HARDWARE_PROFILE_NOTES = {
    "RAM_LIMIT_GB": {
        "description": "Maximum RAM (GB) the runtime may use. Hard limit.",
        "type": "int",
        "valid_range": "1 to system_max; recommended 2 for low-RAM systems.",
        "default": 2,
        "semantic_role": "structural",
        "affects": ["MES_OPTIONS", "RAG_OPTIONS", "PERSISTENCE_MENU"],
        "requires": []
    },
    "ENABLE_SWAP": {
        "description": "Allow swap usage when RAM_LIMIT_GB is approached.",
        "type": "bool",
        "valid_range": "True | False",
        "default": True,
        "semantic_role": "structural",
        "affects": ["MES_OPTIONS"],
        "requires": ["RAM_LIMIT_GB"]
    },
    "CPU_PRIORITY_MODE": {
        "description": "CPU scheduling priority for runtime processes.",
        "type": "enum",
        "valid_range": "LOW | BALANCED | HIGH | REALTIME",
        "default": "BALANCED",
        "semantic_role": "computational",
        "affects": ["MES_OPTIONS"],
        "requires": []
    },
    "GPU_ACCELERATION": {
        "description": "Enable GPU acceleration for model inference where available.",
        "type": "bool",
        "valid_range": "True | False",
        "default": False,
        "semantic_role": "structural",
        "affects": ["MODEL_ROUTING"],
        "requires": []
    }
}


# --------------------------------------------------

"""
==================================================
[ FRAGMENT 6 — HOMEGROWN_OPTIONS ]
==================================================

Purpose:
Declares HomeGrown ecosystem residency
parameters. Provides residency context for
Eidouron-scale Conceptual AIs.

Operational role: structural (where things
live in the architecture).
==================================================
"""

HOMEGROWN_OPTIONS = {
    "ENABLE_SYMBOLIC_LAYER": True,
    "ENABLE_MEMORY_TRANSLATION": True,
    "ENABLE_FRAGMENT_ROUTING": True,
    "MAX_ACTIVE_FRAGMENTS": 2
}

HOMEGROWN_OPTIONS_NOTES = {
    "ENABLE_SYMBOLIC_LAYER": {
        "description": "Enable Runic symbolic operations within HomeGrown ecosystem.",
        "type": "bool",
        "valid_range": "True | False",
        "default": True,
        "semantic_role": "semantic",
        "affects": [],
        "requires": []
    },
    "ENABLE_MEMORY_TRANSLATION": {
        "description": "Enable cross-module memory translation (Eidouron-Eidoneura bridging).",
        "type": "bool",
        "valid_range": "True | False",
        "default": True,
        "semantic_role": "structural",
        "affects": [],
        "requires": ["ENABLE_SYMBOLIC_LAYER"]
    },
    "ENABLE_FRAGMENT_ROUTING": {
        "description": "Enable fragment-level routing within HomeGrown ecosystem.",
        "type": "bool",
        "valid_range": "True | False",
        "default": True,
        "semantic_role": "computational",
        "affects": [],
        "requires": []
    },
    "MAX_ACTIVE_FRAGMENTS": {
        "description": "Maximum HomeGrown fragments active simultaneously.",
        "type": "int",
        "valid_range": "1 to 16; constrained by RAM_LIMIT_GB.",
        "default": 2,
        "semantic_role": "structural",
        "affects": ["HARDWARE_PROFILE"],
        "requires": ["RAM_LIMIT_GB"]
    }
}


# --------------------------------------------------

"""
==================================================
[ FRAGMENT 7 — GRAPH_REPLAY ]
==================================================

Purpose:
Reconstructs prior execution from persistence.
Inverse of PERSISTENCE_MENU; pairs with it as
Same/Same-but-Different (Helix Codex Stage 10
Section XLVI Lens 1).

Operational role: temporal (replay across time).

Note: Mark to confirm operational fields per
Helix Codex Stage 8 fragment catalog discussion.
The fields below are proposed defaults.
==================================================
"""

GRAPH_REPLAY = {
    "REPLAY_DEPTH": 10,
    "STATE_INSPECTION_LEVEL": "STANDARD",
    "FAILURE_RECONSTRUCTION_MODE": "AUTO",
    "REPLAY_LOG_RETENTION": 50
}

GRAPH_REPLAY_NOTES = {
    "REPLAY_DEPTH": {
        "description": "Maximum replay depth (number of historical states traversable).",
        "type": "int",
        "valid_range": "1 to MAX_REPLAY_HISTORY (from PERSISTENCE_MENU).",
        "default": 10,
        "semantic_role": "temporal",
        "affects": ["HARDWARE_PROFILE"],
        "requires": ["PERSISTENCE_MENU.MAX_REPLAY_HISTORY"]
    },
    "STATE_INSPECTION_LEVEL": {
        "description": "Detail level for state inspection during replay.",
        "type": "enum",
        "valid_range": "MINIMAL | STANDARD | DEEP | FULL",
        "default": "STANDARD",
        "semantic_role": "semantic",
        "affects": ["HARDWARE_PROFILE"],
        "requires": []
    },
    "FAILURE_RECONSTRUCTION_MODE": {
        "description": "Strategy for replay reconstruction when state is partially corrupted.",
        "type": "enum",
        "valid_range": "STRICT | AUTO | LENIENT",
        "default": "AUTO",
        "semantic_role": "computational",
        "affects": [],
        "requires": []
    },
    "REPLAY_LOG_RETENTION": {
        "description": "Maximum replay log entries retained.",
        "type": "int",
        "valid_range": "0 to 10000.",
        "default": 50,
        "semantic_role": "temporal",
        "affects": ["HARDWARE_PROFILE"],
        "requires": []
    }
}


# ==================================================
# FRAGMENT REGISTRY
# ==================================================

"""
==================================================
[ FRAGMENT REGISTRY ]
==================================================

Maps fragment names to their dictionary
declarations. The MainMenu builder uses this
mapping to compose runtime state.

NOTES_REGISTRY parallels FRAGMENTS — provides
the OPTION_NOTES for each fragment, used by
validators and operator-facing documentation
surfaces.
==================================================
"""

FRAGMENTS = {
    "MODEL_ROUTING": MODEL_ROUTING,
    "MES": MES_OPTIONS,
    "RAG": RAG_OPTIONS,
    "PERSISTENCE": PERSISTENCE_MENU,
    "HARDWARE": HARDWARE_PROFILE,
    "HOMEGROWN": HOMEGROWN_OPTIONS,
    "GRAPH_REPLAY": GRAPH_REPLAY
}

NOTES_REGISTRY = {
    "MODEL_ROUTING": MODEL_ROUTING_NOTES,
    "MES": MES_OPTIONS_NOTES,
    "RAG": RAG_OPTIONS_NOTES,
    "PERSISTENCE": PERSISTENCE_MENU_NOTES,
    "HARDWARE": HARDWARE_PROFILE_NOTES,
    "HOMEGROWN": HOMEGROWN_OPTIONS_NOTES,
    "GRAPH_REPLAY": GRAPH_REPLAY_NOTES
}


# ==================================================
# MAIN MENU BUILDER
# ==================================================

"""
==================================================
[ MAIN MENU BUILDER ]
==================================================

Composes runtime system from fragments.

Each fragment is loaded as a top-level entry
in system_state. The result is a deterministic
runtime configuration usable by downstream
execution layers.
==================================================
"""


def build_main_menu(fragments):
    """
    Composes runtime system from fragments.
    Deterministic: same inputs always produce same outputs.
    """
    system_state = {}

    for name, fragment in fragments.items():
        system_state[name] = fragment.copy()  # defensive copy

    return system_state


# ==================================================
# CONFIG SAVE / LOAD SYSTEM
# ==================================================

"""
==================================================
[ CONFIGURATION MANAGEMENT ]
==================================================

Responsible for:
- saving runtime state
- loading profiles
- preserving MenuCode structure across sessions
- respecting DEPLOYMENT_CONTEXT for Vanilla/Flavor routing
==================================================
"""


def save_config(state):
    """Persist the assembled MenuCode state to JSON."""
    config = {
        "CURRENT_PROFILE": CURRENT_PROFILE,
        "DEPLOYMENT_CONTEXT": DEPLOYMENT_CONTEXT,
        "FRAGMENTS": state,
    }

    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=4)

    print(f"[+] Configuration saved to {CONFIG_PATH}")


def load_config():
    """Load a previously persisted MenuCode state from JSON, if present."""
    if not os.path.exists(CONFIG_PATH):
        print(f"[!] No prior config found at {CONFIG_PATH}; using defaults.")
        return None

    with open(CONFIG_PATH, "r") as f:
        config = json.load(f)

    print(f"[+] Configuration loaded from {CONFIG_PATH}")
    return config


# ==================================================
# RUNTIME STATUS DISPLAY
# ==================================================

"""
==================================================
[ RUNTIME STATUS ]
==================================================

Human-readable runtime summary.
Future GUI systems can bind directly to these
runtime state objects.
==================================================
"""


def display_runtime_status(state):
    """Print a human-readable summary of the current runtime state."""
    print("\n========================================")
    print(" MENUCODE RUNTIME STATUS")
    print("========================================")
    print(f"Profile: {CURRENT_PROFILE}")
    print(f"Deployment Context: {DEPLOYMENT_CONTEXT}")
    print(f"Active Fragments: {len(state)}")
    for name in state:
        print(f"  - {name}")
    print("========================================\n")


# ==================================================
# SYSTEM EXECUTION LOOP
# ==================================================

"""
==================================================
[ SYSTEM EXECUTION ]
==================================================

Loads each fragment in turn, simulating runtime
startup. In production, this is where downstream
integrations (MES, EGC, graph replay systems,
MenuCode parser systems) would be invoked.
==================================================
"""


def run_system(menu):
    """Simulate runtime startup over the assembled menu."""
    print("\n=== MENUCODE SYSTEM START ===\n")

    for module_name, config in menu.items():
        print(f"Loading Module: {module_name}")
        time.sleep(0.05)  # quicker than the prototype for snappier learning

    print("\nSystem Ready.\n")
    return menu


# ==================================================
# MAIN EXECUTION ENTRY
# ==================================================

"""
==================================================
[ MAIN EXECUTION ]
==================================================

Entry point. Builds the menu, displays status,
runs the system loop, persists state.

Future integrations to add as they come online:
- MES (Model Execution Scheduler)
- EGC (Execution Graph Compiler)
- graph replay systems
- MenuCode parser systems
- Schemata recommendations
- Procedural Bindrune execution
==================================================
"""


if __name__ == "__main__":
    menu = build_main_menu(FRAGMENTS)
    display_runtime_status(menu)
    system = run_system(menu)
    save_config(system)
    print(json.dumps(system, indent=2))

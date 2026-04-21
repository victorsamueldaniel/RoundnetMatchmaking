# Documentation Index

## Core Documents
- `BUILD_INSTRUCTIONS.md`: Windows executable packaging and release artifact workflow.
- `ITERATIONS_IMPLEMENTATION.md`: iteration-specific implementation notes.
- `diagrams/session_creation/SESSION_CREATION_DIAGRAM.md`: generated function/data model summary for session creation.

## Diagram Maintenance
- Source registry: `diagrams/session_creation/session_diagram_registry.json`
- Generator script: `diagrams/session_creation/generate_session_diagram.py`
- Regenerate docs: `python docs/diagrams/session_creation/generate_session_diagram.py`
- Check for drift: `python docs/diagrams/session_creation/generate_session_diagram.py --check`

## Recommended Next Additions
- `ARCHITECTURE.md`: system architecture and data flow.
- `API.md`: public interfaces and extension points.

"""Native framework connectors — a framework's own callbacks become Alfred traces.

Each connector is gated behind an optional extra (e.g. ``alfred-ai[langgraph]``):
importing a connector module requires its extra to be installed, so the core
package keeps its single ``pyyaml`` dependency. See
docs/adr/0014-langgraph-native-connector.md.

This package intentionally imports nothing at top level — importing
``alfred.integrations`` must not pull a framework SDK.
"""

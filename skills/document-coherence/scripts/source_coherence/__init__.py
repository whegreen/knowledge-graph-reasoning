"""source_coherence — mesin quick-check koherensi dokumen, stdlib saja.

Batas paket: tidak mengimpor KG, git, registry proyek, atau skill agent.
Lapisan knowledge management berada di ops/kg/coherence_impact.py.
"""
from . import compare, config, extract, report

__all__ = ["compare", "config", "extract", "report"]

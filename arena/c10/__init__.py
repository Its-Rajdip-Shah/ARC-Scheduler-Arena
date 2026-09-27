"""C10 realistic ARC workload and human-review infrastructure.

Keep package import side-effect free.

The realistic fixture depends on Django-backed planning models, while the
human-diagnostics layer is intentionally able to inspect frozen artifacts
without booting Django. Import concrete C10 modules directly from their
submodules.
"""

__all__ = []

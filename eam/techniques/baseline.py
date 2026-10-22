from eam.techniques.base import Technique


class FullContext(Technique):
    """Baseline: keep everything, no caching hints. Every other technique is compared to this."""

    name = "full"
    source = "baseline"
    provenance = "baseline"

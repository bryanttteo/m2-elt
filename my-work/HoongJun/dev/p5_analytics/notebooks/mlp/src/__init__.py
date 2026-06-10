"""Olist late-delivery / repeat-purchase ML pipeline.

Each stage is a single-responsibility module so the flow lifts cleanly from
``mlp.ipynb`` into a non-interactive run via ``run.sh``:

    config -> ingest -> labels -> features -> model -> evaluate -> pipeline
"""

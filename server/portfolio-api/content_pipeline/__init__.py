"""Source-agnostic content signal pipeline (子系统 A 第一实现).

Detect new items from a SourceAdapter → notify (A) → transcribe + distill
free items into a 信号卡 → deliver (B). See docs/superpowers/specs/
2026-06-14-content-signal-pipeline-design.md.
"""

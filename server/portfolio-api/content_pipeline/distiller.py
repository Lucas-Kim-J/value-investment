"""Transcript → 信号卡 (structured JSON) via the hermes skill vi-podcast-distill.

build_distill_input / parse_signal_card are pure (unit-tested). distill() wires a
runner (subprocess by default) so tests inject a fake. The card schema is
pre-aligned to capture_note for the future Notion (C) hookup."""
from __future__ import annotations

import json
import os
import re
import subprocess

from content_pipeline.models import ContentItem, PILLARS, REQUIRED_CARD_KEYS

_PROFILE = os.environ.get("VI_PIPELINE_PROFILE", "app-lucas")
_SKILL = "vi-podcast-distill"
_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.S)


def build_distill_input(item: ContentItem, transcript: str) -> str:
    """The instruction + transcript handed to the vi-podcast-distill skill."""
    show = item.show_title or "非共识的20分钟"
    return (
        f"播客《{show}》单集：{item.title}\n"
        f"链接：{item.url}\n\n"
        "请按 vi-podcast-distill 技能，把下面的转录蒸馏成一张『信号卡』，"
        "只输出一个 JSON 对象（可包在 ```json 代码块里），字段：\n"
        "- tldr：一句话主旨\n"
        "- non_consensus：他和市场共识具体哪里不一样\n"
        "- new_angle：可迁移到价值投资框架的角度\n"
        f"- pillar：命中的支柱，取值之一 {list(PILLARS)}\n"
        "- caution：他可能错在哪 / 利益相关 / 他重 crypto-宏观的倾向提醒\n"
        '- worth_relisten：{"yes": bool, "timestamps": ["mm:ss 关于…"]}\n'
        "绝不编造内容；转录没讲到的不要硬填。\n\n"
        f"【转录全文】\n{transcript}\n"
    )


def parse_signal_card(raw: str) -> dict:
    """Extract + validate a 信号卡 from hermes output. Raises ValueError if the
    text isn't valid JSON, is missing a required key, or has a bad pillar."""
    text = (raw or "").strip()
    fence = _JSON_FENCE_RE.search(text)
    if fence:
        blob = fence.group(1)
    else:
        start = text.find("{")
        if start == -1:
            raise ValueError("no JSON object found in distiller output")
        blob = text[start:]   # may carry trailing prose; raw_decode reads the first object
    try:
        # raw_decode parses the first complete JSON object and ignores any trailing text,
        # so stray prose containing '}' after the card no longer breaks parsing.
        card, _ = json.JSONDecoder().raw_decode(blob)
    except ValueError as e:
        raise ValueError(f"distiller output is not valid JSON: {e}") from e
    if not isinstance(card, dict):
        raise ValueError("distiller output is not a JSON object")
    missing = [k for k in REQUIRED_CARD_KEYS if k not in card]
    if missing:
        raise ValueError(f"signal card missing keys: {missing}")
    if card["pillar"] not in PILLARS:
        raise ValueError(f"bad pillar: {card['pillar']!r}")
    wr = card.get("worth_relisten")
    if not isinstance(wr, dict) or "yes" not in wr:
        raise ValueError("worth_relisten must be an object with a 'yes' field")
    return card


def _hermes_skill_runner(prompt: str) -> str:
    r = subprocess.run(
        ["hermes", "-p", _PROFILE, "--skills", _SKILL, "-z", prompt],
        capture_output=True, text=True, timeout=300)
    out = (r.stdout or "").strip()
    if r.returncode != 0 or not out:
        raise RuntimeError((r.stderr or "").strip()[-300:] or "hermes 返回空内容")
    return out


class Distiller:
    def __init__(self, runner=_hermes_skill_runner):
        self._runner = runner

    def distill(self, item: ContentItem, transcript: str) -> dict:
        raw = self._runner(build_distill_input(item, transcript))
        return parse_signal_card(raw)

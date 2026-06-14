"""Render + push pipeline messages to Feishu via `hermes send`. render_* are
pure (unit-tested); Deliverer wraps the subprocess with an injectable runner."""
from __future__ import annotations

import os
import subprocess

from content_pipeline.models import ContentItem

_TARGET = os.environ.get("VI_PIPELINE_FEISHU_TARGET", "feishu")


def render_new_notice(item: ContentItem) -> str:
    paid = "（付费集，管道够不着，需自听）" if item.is_paid else ""
    return f"🎙️ 新集{paid}：{item.title}\n{item.url}"


def render_signal_card(item: ContentItem, card: dict) -> str:
    wr = card.get("worth_relisten") or {}
    relisten = "值得回听" if wr.get("yes") else "可跳过"
    stamps = "；".join(wr.get("timestamps") or [])
    lines = [
        f"🧭 信号卡 · {item.title}",
        "",
        f"主旨：{card.get('tldr','')}",
        f"非共识：{card.get('non_consensus','')}",
        f"新角度：{card.get('new_angle','')}",
        f"支柱：{card.get('pillar','')}",
        f"⚠️ 警惕：{card.get('caution','')}",
        f"回听：{relisten}" + (f"（{stamps}）" if stamps else ""),
        "",
        f"原集：{item.url}",
    ]
    return "\n".join(lines)


def _hermes_send(text: str, subject: str) -> None:
    r = subprocess.run(["hermes", "send", "--to", _TARGET, "--subject", subject],
                       input=text, capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        raise RuntimeError("hermes send 失败：" + (r.stderr.strip()[-200:] or "unknown"))


class Deliverer:
    def __init__(self, runner=_hermes_send):
        self._send = runner

    def send_new_notice(self, item: ContentItem) -> None:
        self._send(render_new_notice(item), "🎙️ 非共识的20分钟 · 新集")

    def send_signal_card(self, item: ContentItem, card: dict) -> None:
        self._send(render_signal_card(item, card), "🧭 信号卡 · 非共识的20分钟")

    def send_alert(self, text: str) -> None:
        self._send(text, "⚠️ 内容管道告警")

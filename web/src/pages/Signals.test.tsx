import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

const sample = {
  external_id: "e7", source: "xiaoyuzhou", show_title: "非共识的20分钟",
  image_url: "http://img/cover.jpg", title: "美联储 Ep 7", url: "http://xyz/episode/e7",
  published_at: "2026-06-13T16:00:00.000Z",
  card: { tldr: "盯的不是利率", non_consensus: "市场问错了", new_angle: "盯隐藏变量",
          pillar: "资金传导", caution: "他重 crypto", worth_relisten: { yes: false, timestamps: [] } },
};

vi.mock("../lib/api", () => ({
  apiGet: vi.fn((p: string) =>
    p === "/api/signals"
      ? Promise.resolve({ ok: true, status: 200, data: { items: [sample] } })
      : Promise.resolve({ ok: true, status: 200, data: { ...sample, transcript: "转录全文内容" } })),
}));
vi.mock("../lib/hooks", () => ({ useMe: () => "lucas" }));

import Signals from "./Signals";

describe("Signals", () => {
  beforeEach(() => vi.clearAllMocks());

  it("renders a signal card with title, pillar and tldr", async () => {
    render(<Signals />);
    expect(await screen.findByText("美联储 Ep 7")).toBeInTheDocument();
    expect(screen.getByText("资金传导")).toBeInTheDocument();
    expect(screen.getByText(/盯的不是利率/)).toBeInTheDocument();
  });

  it("expands to show the 6 fields and lazy-loads transcript", async () => {
    const { apiGet } = await import("../lib/api");
    render(<Signals />);
    fireEvent.click(await screen.findByText("美联储 Ep 7"));
    expect(await screen.findByText(/市场问错了/)).toBeInTheDocument();   // non_consensus revealed
    fireEvent.click(screen.getByText(/转录全文/));
    await waitFor(() => expect(screen.getByText(/转录全文内容/)).toBeInTheDocument());
    expect(apiGet).toHaveBeenCalledWith("/api/signals/e7");
  });
});

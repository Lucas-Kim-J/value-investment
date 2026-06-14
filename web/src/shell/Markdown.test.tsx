import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Markdown } from "./Markdown";

describe("Markdown", () => {
  it("renders markdown headings to the DOM", () => {
    render(<Markdown>{"# Hello world"}</Markdown>);
    expect(screen.getByRole("heading", { level: 1, name: "Hello world" })).toBeInTheDocument();
  });
});

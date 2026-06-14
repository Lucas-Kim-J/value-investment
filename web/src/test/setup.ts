import "@testing-library/jest-dom/vitest";
import { afterEach } from "vitest";
import { cleanup } from "@testing-library/react";

// unmount React trees between tests so the jsdom DOM doesn't leak across cases
afterEach(() => cleanup());

import "@testing-library/jest-dom/vitest";

import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

// react-toastify writes to a container the tests do not mount. Stubbing it keeps
// assertions on the page itself rather than on toast side effects.
vi.mock("react-toastify/unstyled", () => ({
  toast: Object.assign(vi.fn(), {
    loading: vi.fn(),
    update: vi.fn(),
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
    info: vi.fn(),
    dismiss: vi.fn(),
  }),
}));

// jsdom implements neither, and the checker calls both after an evaluation.
window.requestAnimationFrame = ((callback: FrameRequestCallback) => {
  callback(0);
  return 0;
}) as typeof window.requestAnimationFrame;
Element.prototype.scrollIntoView = vi.fn();

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

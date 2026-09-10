/**
 * The How it works explainer.
 *
 * Stakeholders and engineers read the same headings. The toggle must actually
 * change the depth of the copy, the example table must keep the fixture
 * numbers, and the stakeholder view must not leak storage internals.
 */

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";

import { HowItWorks } from "@/components/how-it-works";
import { AUDIENCE_STORAGE_KEY } from "@/lib/how-it-works-copy";

function renderExplainer() {
  return render(<HowItWorks />);
}

beforeEach(() => {
  window.localStorage.clear();
});

describe("audience toggle", () => {
  it("starts in the stakeholder reading", () => {
    renderExplainer();
    expect(
      screen.getByRole("heading", { name: /from upload to a chosen standard/i }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /for stakeholders/i })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  it("switches to the engineer reading", async () => {
    const user = userEvent.setup();
    renderExplainer();
    await user.click(screen.getByRole("button", { name: /for engineers/i }));
    expect(
      screen.getByRole("heading", { name: /from post \/api\/check to cosine ranking/i }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /for engineers/i })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  it("persists the engineer reading in localStorage", async () => {
    const user = userEvent.setup();
    const { unmount } = renderExplainer();
    await user.click(screen.getByRole("button", { name: /for engineers/i }));
    expect(window.localStorage.getItem(AUDIENCE_STORAGE_KEY)).toBe("technical");
    unmount();
    renderExplainer();
    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: /from post \/api\/check to cosine ranking/i }),
      ).toBeInTheDocument();
    });
  });
});

describe("copy depth", () => {
  it("keeps np.savez and float32 out of the stakeholder reading", () => {
    renderExplainer();
    const panel = screen.getByRole("region", { name: /from upload to a chosen standard/i });
    expect(panel.textContent).not.toMatch(/np\.savez/);
    expect(panel.textContent).not.toMatch(/float32/);
  });

  it("names np.savez and float32 in the engineer reading", async () => {
    const user = userEvent.setup();
    renderExplainer();
    await user.click(screen.getByRole("button", { name: /for engineers/i }));
    const panel = screen.getByRole("region", {
      name: /from post \/api\/check to cosine ranking/i,
    });
    expect(panel.textContent).toMatch(/np\.savez/);
    expect(panel.textContent).toMatch(/float32/);
  });
});

describe("worked example", () => {
  it("shows the compliant 91.5 match and the 0.8 no-match lead", () => {
    renderExplainer();
    expect(screen.getByRole("table")).toBeInTheDocument();
    expect(screen.getByText("91.5")).toBeInTheDocument();
    expect(screen.getByText("0.8")).toBeInTheDocument();
    expect(screen.getAllByText("no-match").length).toBeGreaterThan(0);
  });
});

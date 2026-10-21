import { expect, test } from "@playwright/test";

const ask = async (page, text: string) => {
  await page.getByRole("textbox", { name: "Your question" }).fill(text);
  await page.getByRole("button", { name: "Ask", exact: true }).click();
};

test("a report with feedback, undo, a follow-up chip and a remember card", async ({ page }) => {
  page.on("dialog", (d) => d.accept());
  await page.goto("/app/?user=alice");
  await ask(page, "customers on hold, i.e. paused");
  const card = page.getByTestId("report").first();
  await expect(card.locator("tbody tr")).toHaveCount(10);
  await expect(card).toContainText("Paused means the stored status paused.");
  // Markdown is rendered, not shown raw: the backticks became a code element
  await expect(card.locator(".assumptions code")).toHaveText("paused");
  await card.getByRole("button", { name: "Yes, this is right" }).click();
  await expect(page.locator("[data-sonner-toast]").first()).toContainText("only tunes the bot for you");
  await expect(card).toContainText("You confirmed this");
  await card.getByRole("button", { name: "Undo my feedback" }).click();
  await expect(card.getByRole("button", { name: "Yes, this is right" })).toBeVisible();
  await page.getByTestId("remember").getByRole("button", { name: "Remember, only for me" }).click();
  await expect(page.getByTestId("remember")).toContainText("Only you are affected");
  await card.getByRole("button", { name: "Closed customers too" }).click();
  await expect(page.getByTestId("report")).toHaveCount(2);
  await expect(page.getByTestId("report").nth(1)).toContainText("Closed customers");
});

test("a clarification answered with a chip, then a correction in words", async ({ page }) => {
  await page.goto("/app/?user=bob");
  await ask(page, "show me customers");
  const clarify = page.getByTestId("clarify");
  await expect(clarify).toContainText("Which customers?");
  await clarify.getByRole("radio", { name: "closed" }).click();
  await clarify.getByRole("button", { name: "Run this" }).click();
  const report = page.getByTestId("report").first();
  await expect(report).toContainText("Closed customers");
  await report.getByRole("button", { name: "No, fix it" }).click();
  await page.getByRole("textbox", { name: "Your question" }).fill("I meant the active ones");
  await page.getByRole("button", { name: "Fix it", exact: true }).click();
  await expect(page.getByTestId("report").nth(1)).toContainText("Active customers");
});

test("a grouped answer can be shown as a chart and back as a table", async ({ page }) => {
  await page.goto("/app/?user=carol");
  await ask(page, "order value per month");
  const card = page.getByTestId("report");
  await expect(card.locator("tbody tr")).toHaveCount(9);
  await card.getByRole("radio", { name: "Chart" }).click();
  await expect(card.locator(".result-chart svg").first()).toBeVisible();
  await card.getByRole("radio", { name: "Table" }).click();
  await expect(card.locator("tbody tr")).toHaveCount(9);
});

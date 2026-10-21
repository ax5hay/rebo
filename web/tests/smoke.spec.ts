import { expect, test } from "@playwright/test";

const ask = async (page, text: string) => {
  await page.getByLabel("Question").fill(text);
  await page.getByRole("button", { name: "Ask" }).click();
};

test("a report with feedback, undo, a follow-up chip and a remember card", async ({ page }) => {
  page.on("dialog", (d) => d.accept());
  await page.goto("/app/?user=alice");
  await ask(page, "customers on hold, i.e. paused");
  const card = page.getByTestId("report").first();
  await expect(card.locator("tbody tr")).toHaveCount(10);
  await expect(card).toContainText("Paused means the stored status 'paused'.");
  await card.getByRole("button", { name: "Yes, this is right" }).click();
  await expect(card).toContainText("only tunes the bot for you");
  await card.getByRole("button", { name: "Undo my feedback" }).click();
  await expect(card.getByRole("button", { name: "Yes, this is right" })).toBeVisible();
  await page.getByTestId("remember").getByRole("button", { name: "Remember (only for me)" }).click();
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
  await clarify.getByRole("button", { name: "closed" }).click();
  await clarify.getByRole("button", { name: "Run" }).click();
  const report = page.getByTestId("report").first();
  await expect(report).toContainText("Closed customers");
  await report.getByRole("button", { name: "No, fix it" }).click();
  await ask(page, "I meant the active ones");
  await expect(page.getByTestId("report").nth(1)).toContainText("Active customers");
});

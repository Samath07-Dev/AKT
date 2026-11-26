import { test, expect } from "@playwright/test";

test.describe("Student End-to-End Portal Journey", () => {
  test("authenticates, submits practice bundle, and verifies dashboard & history", async ({ page }) => {
    // 1. Sign In via /login
    await page.goto("/login");
    await page.waitForLoadState("networkidle");
    await expect(page).toHaveTitle(/Adaptive Knowledge Tracing|Intelligent Tutor/i);

    // Verify login form is present
    const usernameInput = page.locator("#username-input");
    const passwordInput = page.locator("#password-input");
    const signInButton = page.getByRole("button", { name: /Sign In/i });

    await expect(usernameInput).toBeVisible();
    await expect(passwordInput).toBeVisible();

    // Explicitly fill student credentials and verify controlled component state
    await usernameInput.fill("student_s001");
    await expect(usernameInput).toHaveValue("student_s001");

    await passwordInput.fill("demo_pass_123");
    await expect(passwordInput).toHaveValue("demo_pass_123");

    // Submit credentials
    await signInButton.click();

    // Verify redirection to /dashboard
    await page.waitForURL(/\/dashboard/, { timeout: 15000 });
    await expect(page.locator("body")).toContainText(/Adaptive Learning Dashboard|Student Learning Dashboard|Overview|Competencies/i);

    // 2. Navigate to Practice Arena for Variables
    await page.goto("/practice?concept=Variables&difficulty=easy&mode=student");
    await expect(page.locator("body")).toContainText(/Variables/i);

    // Question 1 (MCQ): select first option and click Next Activity
    await page.getByRole("radio").first().click();
    await page.getByRole("button", { name: /Next Activity/i }).click();

    // Question 2 (MCQ): select first option and click Next Activity
    await page.getByRole("radio").first().click();
    await page.getByRole("button", { name: /Next Activity/i }).click();

    // Question 3 (MCQ): select first option and click Next Activity
    await page.getByRole("radio").first().click();
    await page.getByRole("button", { name: /Next Activity/i }).click();

    // Question 4 (Short Answer): fill explanation and click Next Activity
    const saTextarea = page.getByPlaceholder(/Write your explanation here/i);
    await expect(saTextarea).toBeVisible({ timeout: 10000 });
    await saTextarea.fill("Variables in Python act as named references pointing to memory objects.");
    await page.getByRole("button", { name: /Next Activity/i }).click();

    // Question 5 (Coding): Submit 5-Question Bundle
    const submitBtn = page.getByRole("button", { name: /Submit.*Bundle/i });
    await expect(submitBtn).toBeVisible({ timeout: 10000 });
    await submitBtn.click();

    // Verify bundle evaluation summary appears
    await expect(page.locator("body")).toContainText(/Assessment.*Summary|MCQ Correctness|Short Answer/i, { timeout: 20000 });

    // 3. Verify Dashboard Updates
    await page.goto("/dashboard");
    await page.waitForLoadState("networkidle");

    // The Variables concept card should now reflect non-zero attempt / progress
    const variablesKcCard = page.locator("div.rounded-lg").filter({ has: page.locator("span", { hasText: "Variables" }) }).first();
    await expect(variablesKcCard).toBeVisible({ timeout: 15000 });
    await expect(variablesKcCard).toContainText("Variables");
    await expect(variablesKcCard).toContainText(/Focus Area|In Progress|Mastered/);
    await expect(variablesKcCard).not.toContainText("Not Attempted");
    await expect(variablesKcCard).not.toContainText("0.0%");

    // 4. Verify History Log Updates
    await page.goto("/history");
    await page.waitForLoadState("networkidle");

    const historyTable = page.locator("table");
    await expect(historyTable).toBeVisible({ timeout: 15000 });

    const variablesHistoryRow = historyTable.locator('tr:has-text("Variables")').first();
    await expect(variablesHistoryRow).toBeVisible({ timeout: 15000 });

    // Assert row displays valid evaluation details and coding status badge
    const historyRowText = await variablesHistoryRow.textContent();
    expect(historyRowText).toBeTruthy();
    expect(historyRowText).toMatch(/Pending evaluation|passed|\d+%/i);
  });
});

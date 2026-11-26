/**
 * frontend/src/lib/practice-sandbox-ui.ts
 *
 * Pure UI presentation helpers for Practice Arena coding sandbox status,
 * preview vs live Docker test modes, and fail-closed messaging.
 */

export type SandboxConnectionStatus = "checking" | "available" | "offline";
export type CodeResultMode =
  | "none"
  | "syntax_preview"
  | "docker_executed"
  | "pending_offline";

export interface PracticeSandboxPresentation {
  badgeVariant: "success" | "default" | "warning";
  badgeLabel: string;
  editorDotClass: string;
  cardDescription: string;
  panelTitle: string;
  panelNotice: string;
  canRunDockerTests: boolean;
  counterLabel: string | null;
}

export function getPracticeSandboxPresentation(input: {
  sandboxStatus: SandboxConnectionStatus;
  resultMode: CodeResultMode;
  isSubmitted: boolean;
  testsPassed: number;
  testsTotal: number;
  codeScore?: number | null;
}): PracticeSandboxPresentation {
  const {
    sandboxStatus,
    resultMode,
    isSubmitted,
    testsPassed,
    testsTotal,
    codeScore,
  } = input;

  const isAvailable = sandboxStatus === "available";
  const isChecking = sandboxStatus === "checking";

  const badgeVariant: "success" | "default" | "warning" = isAvailable
    ? "success"
    : isChecking
    ? "default"
    : "warning";

  const badgeLabel = isAvailable
    ? "Docker Sandbox Ready"
    : isChecking
    ? "Checking Sandbox..."
    : "Sandbox Offline (Preview Only)";

  const editorDotClass = isAvailable
    ? "bg-emerald-400"
    : isChecking
    ? "bg-slate-400 animate-pulse"
    : "bg-amber-400";

  const cardDescription = isAvailable
    ? "Write Python solution code below. Automated tests run inside an isolated, network-disabled Docker container. Use Check Code Syntax (Preview) for instant structure checks or Run Tests (Docker Sandbox) for live execution."
    : isChecking
    ? "Write Python solution code below. Verifying live Docker Python sandbox availability with the backend..."
    : "Write Python solution code below. Isolated Docker execution is currently offline or unavailable. Syntax preview checks structure only; automated test grading is deferred as pending secure evaluation.";

  let panelTitle: string;
  let panelNotice: string;
  let counterLabel: string | null = null;

  if (resultMode === "docker_executed") {
    panelTitle = "Isolated Docker Sandbox Results";
    panelNotice = isSubmitted
      ? "Submitted Python code was executed against authoritative server-side test cases inside an ephemeral, network-isolated Docker container."
      : "Code executed against authoritative server-side test cases inside an ephemeral, network-isolated Docker container (preview check; score not recorded yet).";
    const scoreSuffix =
      typeof codeScore === "number" ? ` · ${codeScore.toFixed(1)}%` : "";
    counterLabel = `Passed: ${testsPassed} / ${testsTotal} (Docker Sandbox)${scoreSuffix}`;
  } else if (resultMode === "syntax_preview") {
    panelTitle = "Syntax & Structure Preview (Not Executed)";
    panelNotice = isAvailable
      ? "Syntax & structure preview only — Python code has NOT been executed in Docker yet. Click 'Run Tests (Docker Sandbox)' to run real tests."
      : "Syntax & structure preview only — secure Docker execution is unavailable, so code was checked for structure only.";
    counterLabel = `Preview: ${testsPassed} / ${testsTotal} (Syntax Preview Only)`;
  } else if (resultMode === "pending_offline") {
    panelTitle = "Python Execution Pending (Sandbox Offline)";
    panelNotice =
      "Secure Docker execution was unavailable during evaluation. Automated tests remain Not Performed (Pending Secure Evaluation).";
    counterLabel = "Execution: Not Performed (Pending Secure Evaluation)";
  } else if (isAvailable) {
    panelTitle = "Docker Sandbox Test Specifications";
    panelNotice =
      "Isolated Docker Python sandbox is ready. Click 'Run Tests (Docker Sandbox)' to execute your code against server-side tests, or 'Check Code Syntax (Preview)' for an instant structure check.";
  } else if (isChecking) {
    panelTitle = "Checking Docker Sandbox Status";
    panelNotice =
      "Verifying live Docker Python sandbox readiness with the FastAPI backend...";
  } else {
    panelTitle = "Syntax & Formatting Check (Sandbox Offline)";
    panelNotice =
      "Secure Python sandbox is currently offline or unavailable. Syntax preview checks code structure only; actual execution is deferred as pending secure evaluation.";
  }

  return {
    badgeVariant,
    badgeLabel,
    editorDotClass,
    cardDescription,
    panelTitle,
    panelNotice,
    canRunDockerTests: !isSubmitted && isAvailable,
    counterLabel,
  };
}


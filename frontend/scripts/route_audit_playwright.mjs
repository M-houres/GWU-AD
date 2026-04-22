import fs from "node:fs/promises";
import path from "node:path";
import process from "node:process";

import { chromium } from "playwright";

const FRONTEND_BASE = process.env.FRONTEND_BASE || "http://127.0.0.1:5173";
const API_BASE = process.env.API_BASE || "http://127.0.0.1:8000";

const TEST_ADMIN = {
  username: process.env.ADMIN_USERNAME || "admin",
  password: process.env.ADMIN_PASSWORD || "admin123456",
};
const TEST_USER_OPENID = process.env.TEST_USER_OPENID || "demo_view_user_001";

const PUBLIC_ROUTES = ["/", "/home", "/login", "/register", "/admin/login"];
const USER_ROUTES = [
  "/detect",
  "/dedup",
  "/rewrite",
  "/review",
  "/defense",
  "/history",
  "/buy",
  "/credits",
  "/profile",
  "/referral",
  "/app/history",
  "/app/credits",
  "/app/detect",
  "/app/detect/records",
  "/app/dedup",
  "/app/dedup/records",
  "/app/rewrite",
  "/app/rewrite/records",
  "/app/review",
  "/app/defense",
  "/app/referral",
  "/app/buy",
  "/app/profile",
  "/app/profile?tab=history",
  "/app/profile?tab=credits",
];
const ADMIN_ROUTES = [
  "/admin",
  "/admin/dashboard",
  "/admin/users",
  "/admin/users/1",
  "/admin/tasks",
  "/admin/orders",
  "/admin/referrals",
  "/admin/configs",
  "/admin/configs/notice",
  "/admin/configs/miniapp",
  "/admin/logs",
  "/admin/admin-users",
];

function ts() {
  const d = new Date();
  const p = (v) => String(v).padStart(2, "0");
  return `${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}_${p(d.getHours())}${p(d.getMinutes())}${p(d.getSeconds())}`;
}

async function ensureDir(dirPath) {
  await fs.mkdir(dirPath, { recursive: true });
}

async function apiRequest(url, options = {}) {
  const response = await fetch(url, options);
  const text = await response.text();
  let json;
  try {
    json = JSON.parse(text);
  } catch {
    json = null;
  }
  return { response, text, json };
}

async function getAdminSession() {
  const { response, text, json } = await apiRequest(`${API_BASE}/api/v1/admin/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(TEST_ADMIN),
  });
  if (!response.ok) {
    throw new Error(`admin login http=${response.status} body=${text.slice(0, 300)}`);
  }
  if (!json || json.code !== 0 || !json?.data?.token) {
    throw new Error(`admin login biz failed: ${text.slice(0, 300)}`);
  }
  return {
    token: json.data.token,
    adminInfo: json.data.admin || null,
  };
}

async function getUserSession() {
  const qrcode = await apiRequest(`${API_BASE}/api/v1/auth/wx/qrcode`);
  if (!qrcode.response.ok || !qrcode.json || qrcode.json.code !== 0 || !qrcode?.json?.data?.key) {
    throw new Error(`wx qrcode failed: http=${qrcode.response.status}, body=${qrcode.text.slice(0, 300)}`);
  }
  const key = qrcode.json.data.key;

  const mock = await apiRequest(`${API_BASE}/api/v1/auth/wx/mock-authorize`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ key, openid: TEST_USER_OPENID }),
  });
  if (!mock.response.ok || !mock.json || mock.json.code !== 0) {
    throw new Error(`wx mock failed: http=${mock.response.status}, body=${mock.text.slice(0, 300)}`);
  }

  for (let i = 0; i < 30; i += 1) {
    const poll = await apiRequest(`${API_BASE}/api/v1/auth/wx/poll/${key}`);
    if (poll.response.ok && poll.json?.code === 0 && poll.json?.data?.status === "authorized" && poll.json?.data?.token) {
      return {
        token: poll.json.data.token,
        userInfo: poll.json.data.user || null,
      };
    }
    await new Promise((r) => setTimeout(r, 500));
  }
  throw new Error("wx poll timeout");
}

function shouldIgnoreHttpError(url, status) {
  if (status < 400) return true;
  if (url.includes("/favicon.ico")) return true;
  if (url.includes("/__vite_ping")) return true;
  if (url.includes("@vite/client")) return true;
  return false;
}

function routeTag(route) {
  return route
    .replace(/^\//, "")
    .replace(/[/?=&]/g, "_")
    .replace(/_+/g, "_")
    .replace(/^$/, "root");
}

async function auditOneRoute({
  browser,
  route,
  group,
  storage,
  screenshotDir,
}) {
  const context = await browser.newContext();
  if (storage && typeof storage === "object") {
    await context.addInitScript((entries) => {
      Object.entries(entries).forEach(([k, v]) => {
        window.localStorage.setItem(k, v);
      });
    }, storage);
  }
  const page = await context.newPage();

  const consoleErrors = [];
  const pageErrors = [];
  const httpErrors = [];
  const notes = [];

  page.on("console", (msg) => {
    if (msg.type() === "error") {
      consoleErrors.push(msg.text());
    }
  });
  page.on("pageerror", (err) => {
    pageErrors.push(String(err));
  });
  page.on("response", (resp) => {
    const status = resp.status();
    const url = resp.url();
    if (!shouldIgnoreHttpError(url, status) && status >= 400) {
      httpErrors.push({ status, url });
    }
  });

  const result = {
    group,
    route,
    ok: true,
    final_url: "",
    title: "",
    has_root: false,
    body_text_len: 0,
    console_error_count: 0,
    page_error_count: 0,
    http_error_count: 0,
    notes: [],
    fail_reasons: [],
    screenshot: "",
  };

  try {
    await page.goto(`${FRONTEND_BASE}${route}`, { waitUntil: "domcontentloaded", timeout: 35000 });
    try {
      await page.waitForLoadState("networkidle", { timeout: 10000 });
    } catch {
      notes.push("networkidle_timeout");
    }
    await page.waitForTimeout(500);

    result.final_url = page.url();
    result.title = await page.title();
    result.has_root = await page.locator("#app").count().then((v) => v > 0);
    result.body_text_len = await page.evaluate(() => (document.body?.innerText || "").trim().length);

    if (group === "user" && result.final_url.includes("/login")) {
      result.fail_reasons.push("unexpected_redirect_to_login");
    }
    if (group === "admin" && result.final_url.includes("/admin/login")) {
      result.fail_reasons.push("unexpected_redirect_to_admin_login");
    }
    if (!result.has_root) {
      result.fail_reasons.push("missing_app_root");
    }
    if (result.body_text_len < 20) {
      result.fail_reasons.push("body_text_too_short");
    }

    // Light page-structure checks for task chain pages.
    if (route.includes("/app/detect") || route.includes("/app/dedup") || route.includes("/app/rewrite")) {
      if (!route.includes("/records")) {
        const hasFileInput = await page.locator('input[type="file"]').count().then((v) => v > 0);
        if (!hasFileInput) {
          notes.push("no_file_input_found_on_submit_page");
        }
      } else {
        const hasListLike = await page
          .evaluate(() => !!document.querySelector("table, [class*='record'], [class*='list'], [class*='task']"));
        if (!hasListLike) {
          notes.push("no_list_component_detected_on_records_page");
        }
      }
    }
  } catch (error) {
    result.fail_reasons.push(`navigation_exception:${String(error).slice(0, 260)}`);
  }

  result.console_error_count = consoleErrors.length;
  result.page_error_count = pageErrors.length;
  result.http_error_count = httpErrors.length;

  if (consoleErrors.length > 0) {
    result.fail_reasons.push("console_error");
  }
  if (pageErrors.length > 0) {
    result.fail_reasons.push("page_error");
  }
  if (httpErrors.length > 0) {
    result.fail_reasons.push("http_error");
  }

  result.notes = notes;
  result.ok = result.fail_reasons.length === 0;

  if (!result.ok) {
    const shotPath = path.join(screenshotDir, `${group}_${routeTag(route)}.png`);
    try {
      await page.screenshot({ path: shotPath, fullPage: true });
      result.screenshot = shotPath;
    } catch {
      // noop
    }
  }

  await context.close();
  return {
    ...result,
    console_errors: consoleErrors.slice(0, 12),
    page_errors: pageErrors.slice(0, 12),
    http_errors: httpErrors.slice(0, 20),
  };
}

async function main() {
  const startedAt = new Date().toISOString();
  const stamp = ts();
  const projectRoot = path.resolve(process.cwd(), "..");
  const reportDir = path.join(projectRoot, "logs");
  const screenshotDir = path.join(projectRoot, "output", "playwright", `route-audit-${stamp}`);
  await ensureDir(reportDir);
  await ensureDir(screenshotDir);

  const adminSession = await getAdminSession();
  const userSession = await getUserSession();

  const publicStorage = {};
  const userStorage = {
    wuhong_user_token: userSession.token,
    wuhong_user_info: JSON.stringify(userSession.userInfo || {}),
  };
  const adminStorage = {
    wuhong_admin_token: adminSession.token,
    wuhong_admin_info: JSON.stringify(adminSession.adminInfo || {}),
  };

  const browser = await chromium.launch({ headless: true });
  const results = [];

  for (const route of PUBLIC_ROUTES) {
    const item = await auditOneRoute({ browser, route, group: "public", storage: publicStorage, screenshotDir });
    results.push(item);
  }
  for (const route of USER_ROUTES) {
    const item = await auditOneRoute({ browser, route, group: "user", storage: userStorage, screenshotDir });
    results.push(item);
  }
  for (const route of ADMIN_ROUTES) {
    const item = await auditOneRoute({ browser, route, group: "admin", storage: adminStorage, screenshotDir });
    results.push(item);
  }

  await browser.close();

  const total = results.length;
  const failed = results.filter((x) => !x.ok);
  const passed = total - failed.length;
  const byGroup = ["public", "user", "admin"].map((group) => {
    const rows = results.filter((x) => x.group === group);
    const fail = rows.filter((x) => !x.ok).length;
    return { group, total: rows.length, passed: rows.length - fail, failed: fail };
  });

  const report = {
    started_at: startedAt,
    finished_at: new Date().toISOString(),
    frontend_base: FRONTEND_BASE,
    api_base: API_BASE,
    user_identity: {
      id: userSession.userInfo?.id || null,
      phone: userSession.userInfo?.phone || "",
      nickname: userSession.userInfo?.nickname || "",
    },
    summary: {
      total_routes: total,
      passed_routes: passed,
      failed_routes: failed.length,
      by_group: byGroup,
    },
    failed_routes: failed.map((x) => ({
      group: x.group,
      route: x.route,
      final_url: x.final_url,
      fail_reasons: x.fail_reasons,
      screenshot: x.screenshot,
      console_errors: x.console_errors,
      page_errors: x.page_errors,
      http_errors: x.http_errors,
    })),
    routes: results,
    artifacts: {
      screenshot_dir: screenshotDir,
    },
  };

  const reportPath = path.join(reportDir, `route_audit_${stamp}.json`);
  await fs.writeFile(reportPath, JSON.stringify(report, null, 2), "utf-8");

  console.log(
    JSON.stringify(
      {
        report_path: reportPath,
        summary: report.summary,
        failed_routes: report.failed_routes.map((x) => `${x.group}:${x.route}`),
      },
      null,
      2,
    ),
  );

  if (failed.length > 0) {
    process.exitCode = 1;
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});

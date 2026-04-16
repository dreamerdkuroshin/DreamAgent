import { Router, type IRouter } from "express";

const router: IRouter = Router();

const BACKEND = process.env.BACKEND_URL || "http://localhost:8001";

/**
 * Generic proxy helper — forwards request body (if any) to the target URL
 * and pipes the response back to the client.
 */
async function proxy(
  targetUrl: string,
  method: string,
  body?: unknown,
  res?: import("express").Response
): Promise<void> {
  const fetchOpts: RequestInit = { method };
  if (body !== undefined && method !== "GET") {
    fetchOpts.headers = { "Content-Type": "application/json" };
    fetchOpts.body = JSON.stringify(body);
  }

  const upstream = await fetch(targetUrl, fetchOpts);
  const json = await upstream.json().catch(() => ({}));
  (res as any).status(upstream.status).json(json);
}

// ── API-Key Settings ──────────────────────────────────────────────────────────

/**
 * POST /api/v1/settings/keys
 * Was previously forwarding to the non-existent /api/config/update.
 * Now correctly targets the new FastAPI settings endpoint.
 */
router.post("/v1/settings/keys", async (req, res) => {
  try {
    await proxy(`${BACKEND}/api/v1/settings/keys`, "POST", req.body, res);
  } catch (error) {
    console.error("Failed to save settings keys:", error);
    res.status(502).json({ success: false, error: "Could not reach backend to save settings" });
  }
});

/**
 * GET /api/v1/settings/keys — retrieve current key status (masked)
 */
router.get("/v1/settings/keys", async (req, res) => {
  try {
    await proxy(`${BACKEND}/api/v1/settings/keys`, "GET", undefined, res);
  } catch (error) {
    res.status(502).json({ success: false, error: "Could not reach backend" });
  }
});

// ── Integrations proxy (bot tokens, task queue, shell) ────────────────────────
// Frontend calls /api/integrations/* (no /v1/ prefix).
// These need to be forwarded to /api/v1/integrations/* on the FastAPI backend.

router.get("/integrations/tokens", async (req, res) => {
  try { await proxy(`${BACKEND}/api/v1/integrations/tokens`, "GET", undefined, res); }
  catch { res.status(502).json({ error: "Cannot reach backend" }); }
});

router.post("/integrations/tokens", async (req, res) => {
  try { await proxy(`${BACKEND}/api/v1/integrations/tokens`, "POST", req.body, res); }
  catch { res.status(502).json({ error: "Cannot reach backend" }); }
});

router.post("/integrations/start/:platform", async (req, res) => {
  try { await proxy(`${BACKEND}/api/v1/integrations/start/${req.params.platform}`, "POST", undefined, res); }
  catch { res.status(502).json({ error: "Cannot reach backend" }); }
});

router.post("/integrations/stop/:platform", async (req, res) => {
  try { await proxy(`${BACKEND}/api/v1/integrations/stop/${req.params.platform}`, "POST", undefined, res); }
  catch { res.status(502).json({ error: "Cannot reach backend" }); }
});

router.get("/integrations/queue", async (req, res) => {
  try { await proxy(`${BACKEND}/api/v1/integrations/queue`, "GET", undefined, res); }
  catch { res.status(502).json({ error: "Cannot reach backend" }); }
});

router.post("/integrations/shell", async (req, res) => {
  try { await proxy(`${BACKEND}/api/v1/integrations/shell?confirm=true`, "POST", req.body, res); }
  catch { res.status(502).json({ error: "Cannot reach backend" }); }
});

// ── Provider connector redirects ──────────────────────────────────────────────

router.post("/connect/:provider", async (req, res) => {
  const { provider } = req.params;
  try {
    const url =
      provider === "stripe" || provider === "telegram"
        ? `${BACKEND}/api/${provider}/connect`
        : `${BACKEND}/api/connect/${provider}`;
    const upstream = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req.body),
    });
    res.status(upstream.status).json(await upstream.json().catch(() => ({})));
  } catch (error) {
    console.error(`Failed to connect ${provider}:`, error);
    res.status(502).json({ error: "Could not reach backend for connector" });
  }
});

export default router;

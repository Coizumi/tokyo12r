const TOKEN_URL = "https://api.customer.jp/oauth/v1/accesstokens";
const INSTANCE_LIST_URL = "https://api.customer.jp/webarenaIndigo/v1/vm/getinstancelist";
const STATUS_UPDATE_URL = "https://api.customer.jp/webarenaIndigo/v1/vm/instance/statusupdate";

const START_CRON = "0 13 * * 5";
const STOP_CRON = "0 9 * * 2";

function requireEnv(env, name) {
  const value = env[name];
  if (!value) {
    throw new Error(`${name} is not configured`);
  }
  return value;
}

function actionForCron(cron) {
  if (cron === START_CRON) return "start";
  if (cron === STOP_CRON) return "stop";
  throw new Error(`Unsupported cron: ${cron}`);
}

async function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function parseJsonResponse(response, label) {
  const text = await response.text();
  let payload;
  try {
    payload = text ? JSON.parse(text) : {};
  } catch (error) {
    throw new Error(`${label} returned non-JSON: ${response.status} ${text.slice(0, 300)}`);
  }
  if (!response.ok) {
    throw new Error(`${label} failed: ${response.status} ${JSON.stringify(safeApiPayload(payload))}`);
  }
  return payload;
}

function safeApiPayload(payload) {
  const safe = {};
  for (const key of ["success", "message", "sucessCode", "instanceStatus", "errorCode", "errorMessage", "developerMessage", "requestId"]) {
    if (payload[key] !== undefined) safe[key] = payload[key];
  }
  return safe;
}

async function createAccessToken(env) {
  const response = await fetch(TOKEN_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      grantType: "client_credentials",
      clientId: requireEnv(env, "WEBARENA_API_KEY"),
      clientSecret: requireEnv(env, "WEBARENA_API_SECRET"),
      code: "",
    }),
  });
  const payload = await parseJsonResponse(response, "access token request");
  if (!payload.accessToken) {
    throw new Error(`access token missing: ${JSON.stringify(safeApiPayload(payload))}`);
  }
  return payload.accessToken;
}

async function listInstance(token, instanceId) {
  const response = await fetch(INSTANCE_LIST_URL, {
    method: "GET",
    headers: { Authorization: `Bearer ${token}` },
  });
  const payload = await parseJsonResponse(response, "instance list request");
  const instances = Array.isArray(payload) ? payload : (payload.instances || payload.instance || payload.data || []);
  return instances.find((item) => String(item.id) === String(instanceId) || String(item.sequence_id) === String(instanceId)) || null;
}

function isAlreadyInDesiredState(instance, action) {
  const status = String(instance?.instanceStatus || instance?.instancestatus || instance?.status || "").toLowerCase();
  if (action === "start") return status.includes("running") || status.includes("active");
  if (action === "stop") return status.includes("stopped") || status.includes("shutoff");
  return false;
}

function acceptedStatusUpdate(payload, action) {
  const code = payload.sucessCode || payload.successCode || "";
  if (payload.success === true) return true;
  if (action === "start" && code === "I20008") return true;
  if (action === "stop" && ["I10025", "I20009"].includes(code)) return true;
  return false;
}

async function updateInstanceStatus(token, instanceId, action) {
  const response = await fetch(STATUS_UPDATE_URL, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify({
      instanceId: String(instanceId),
      status: action,
    }),
  });
  const payload = await parseJsonResponse(response, "instance status update request");
  if (!acceptedStatusUpdate(payload, action)) {
    throw new Error(`instance ${action} was not accepted: ${JSON.stringify(safeApiPayload(payload))}`);
  }
  return payload;
}

async function waitForDesiredState(token, instanceId, action) {
  let current = null;
  for (let attempt = 0; attempt < 6; attempt += 1) {
    await wait(attempt === 0 ? 5000 : 10000);
    current = await listInstance(token, instanceId);
    if (current && isAlreadyInDesiredState(current, action)) {
      return {
        reached: true,
        attempts: attempt + 1,
        state: current.instanceStatus || current.instancestatus || current.status || "unknown",
      };
    }
  }
  return {
    reached: false,
    attempts: 6,
    state: current?.instanceStatus || current?.instancestatus || current?.status || "unknown",
  };
}

async function runPowerAction(env, action, cron = "manual") {
  const instanceId = requireEnv(env, "WEBARENA_INSTANCE_ID");
  const token = await createAccessToken(env);
  await wait(1200);

  const before = await listInstance(token, instanceId);
  if (!before) {
    throw new Error(`instance not found: ${instanceId}`);
  }
  if (isAlreadyInDesiredState(before, action)) {
    return {
      ok: true,
      cron,
      action,
      skipped: true,
      before: before.instanceStatus || before.instancestatus || before.status,
    };
  }

  await wait(1200);
  const result = await updateInstanceStatus(token, instanceId, action);
  const after = await waitForDesiredState(token, instanceId, action);

  return {
    ok: true,
    cron,
    action,
    accepted: safeApiPayload(result),
    before: before.instanceStatus || before.instancestatus || before.status,
    after: after.state,
    reached: after.reached,
    attempts: after.attempts,
  };
}

export default {
  async scheduled(controller, env, ctx) {
    ctx.waitUntil(runPowerAction(env, actionForCron(controller.cron), controller.cron));
  },

  async fetch(request, env) {
    const adminToken = env.ADMIN_TOKEN;
    if (!adminToken || request.headers.get("Authorization") !== `Bearer ${adminToken}`) {
      return new Response("Not found\n", { status: 404, headers: { "Content-Type": "text/plain; charset=utf-8" } });
    }
    const url = new URL(request.url);
    const action = url.searchParams.get("action");
    if (!["start", "stop"].includes(action)) {
      return new Response("Use ?action=start or ?action=stop\n", { status: 400, headers: { "Content-Type": "text/plain; charset=utf-8" } });
    }
    const result = await runPowerAction(env, action);
    return Response.json(result);
  },
};

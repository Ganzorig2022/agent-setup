#!/usr/bin/env node
const crypto = require("crypto");
const fs = require("fs");
const path = require("path");

loadEnvFile(".env.smoke");

const required = [
  "SMOKE_UPLOAD_URL",
  "SMOKE_MICRO_TOKEN",
  "SMOKE_SERVICE",
  "SMOKE_DIRNAME",
  "SMOKE_FILE"
];
const missing = required.filter((key) => !process.env[key]);

if (missing.length > 0) {
  console.error(`Missing required env: ${missing.join(", ")}`);
  process.exit(1);
}

async function main() {
  const filePath = process.env.SMOKE_FILE;
  const file = await fs.promises.readFile(filePath);
  const form = new FormData();
  const uploadPath = new URL(process.env.SMOKE_UPLOAD_URL).pathname.replace(/^\/micro\//, "");
  const msId = crypto.randomUUID();
  const smokeUser = { id: process.env.SMOKE_USER_ID || "smoke-upload-security" };
  const now = new Date();
  const dbSession = buildDbSession(smokeUser.id, now);

  const multipart = {
    session: [
      "MICRO",
      ["DB_SESSION", dbSession],
      ["MS_SESSION", msId, true, null, msId],
      null,
      smokeUser,
      null,
      "127.0.0.1",
      "POST",
      uploadPath
    ],
    body: {
      service: process.env.SMOKE_SERVICE,
      dirname: process.env.SMOKE_DIRNAME,
      note: process.env.SMOKE_NOTE || "upload security smoke"
    }
  };

  form.set(process.env.SMOKE_FILE_FIELD || "content", new Blob([file]), path.basename(filePath));
  form.set("multipart", JSON.stringify(multipart));

  const response = await fetch(process.env.SMOKE_UPLOAD_URL, {
    method: "POST",
    headers: {
      Authorization: `Micro ${getMicroToken(process.env.SMOKE_MICRO_TOKEN)}`
    },
    body: form
  });

  const body = await response.text();
  console.log(`status=${response.status}`);
  console.log(body);

  if (!response.ok) process.exit(1);
}

function buildDbSession(userId, date) {
  return {
    create: {
      created_date: date,
      created_by: userId,
      updated_date: date,
      updated_by: userId,
      status: true
    },
    update: {
      updated_date: date,
      updated_by: userId
    },
    find: {
      status: true
    },
    remove: {
      updated_date: date,
      updated_by: userId,
      status: false
    }
  };
}

function getMicroToken(value) {
  if ((value.match(/\./g) || []).length === 2) return value;
  return signJwt({ name: "qpay-micro-smoke" }, value);
}

function signJwt(payload, secret) {
  const header = { alg: "HS256", typ: "JWT" };
  const body = { ...payload, iat: Math.floor(Date.now() / 1000) };
  const encodedHeader = base64Url(JSON.stringify(header));
  const encodedBody = base64Url(JSON.stringify(body));
  const signature = crypto
    .createHmac("sha256", secret)
    .update(`${encodedHeader}.${encodedBody}`)
    .digest("base64url");

  return `${encodedHeader}.${encodedBody}.${signature}`;
}

function base64Url(value) {
  return Buffer.from(value).toString("base64url");
}

function loadEnvFile(filePath) {
  if (!fs.existsSync(filePath)) return;

  fs.readFileSync(filePath, "utf8")
    .split(/\r?\n/)
    .forEach((line) => {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith("#")) return;

      const separator = trimmed.indexOf("=");
      if (separator === -1) return;

      const key = trimmed.slice(0, separator).trim();
      const value = trimmed.slice(separator + 1).trim().replace(/^["']|["']$/g, "");
      if (!process.env[key]) process.env[key] = value;
    });
}

main().catch((err) => {
  console.error(err.message);
  if (err.cause) console.error(err.cause.code || err.cause.message);
  process.exit(1);
});

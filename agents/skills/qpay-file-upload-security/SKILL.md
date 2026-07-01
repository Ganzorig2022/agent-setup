---
name: qpay-file-upload-security
description: Use when hardening, implementing, or reviewing QPay file upload services as file acceptance boundaries, including byte-based type detection, safe storage names, image CDR, PDF/XLSX risk checks, ClamAV rollout, public read compatibility, and safe negative testing.
---

# QPay File Upload Security

## Purpose

Use this skill when a QPay service accepts user-supplied files. Treat the upload endpoint as a file acceptance boundary: untrusted bytes must be classified, constrained, normalized or inspected, and either rejected before persistence or stored under server-controlled names.

This is separate from QPay microservice smoke mechanics. Use `qpay-micro-smoke` only for `/micro` auth/session request construction.

## Boundary Rules

- Never trust browser MIME type, extension, or original filename. Detect type from bytes.
- Never use original filenames in storage paths or public URLs. Generate UUID names and derive the extension from detected type.
- Enforce size limits before expensive parsing and again after any transformation.
- Reject missing, truncated, ambiguous, or multi-file uploads unless the endpoint explicitly supports multiple files.
- Persist only accepted files. Do not quarantine blocked files unless a reviewed incident-response design requires it.
- Keep service functions plain-data oriented. Validate route/request shape at the boundary.
- Preserve old public reads intentionally when compatibility requires it, but make new writes safer.

## Recommended Type Policy

For internal QPay document/image stores, start narrow:

- Images: JPEG, PNG, WebP. Decode and re-encode with Sharp or equivalent CDR. Strip metadata. Reject corrupt/non-decodable images.
- PDF: Allow only with clear business need. Header/marker regex checks are not full CDR. Prefer a real sanitizer/rewrite path; otherwise document residual risk. Reject encrypted PDFs, embedded files, JavaScript, launch/open actions, rich media, and obvious active content where detectable.
- XLSX: Validate as ZIP and require workbook markers. Reject macros (`xl/vbaProject.bin`), OLE embeddings, external links, ActiveX, path traversal entries, too many entries, excessive uncompressed size, and suspicious compression ratios. Structural validation is not workbook CDR; document formulas/hyperlink residual risk.

## ClamAV

ClamAV is antivirus defense-in-depth, not the main boundary. It helps catch known malware inside otherwise valid-looking files.

- Default can be disabled for phased rollout.
- When enabled, fail closed on timeout, unavailable daemon, or positive detection.
- Support both TCP (`CLAMAV_HOST`, `CLAMAV_PORT`) and Unix socket (`CLAMAV_SOCKET`) because QPay deploys across PM2 VM and Kubernetes styles.
- Do not use live malware for testing. Use EICAR only after DevOps confirms ClamAV is enabled.

## Storage And Database

- Generate a record id and a separate safe filename UUID.
- Build paths only from trusted base path, validated service/dirname segments, record id, and safe filename.
- Prefer writing accepted bytes with exclusive create semantics. If DB create fails after file write, remove the just-written file.
- If DB row must be created before file write for local convention, handle cleanup on write failure.
- For old-core Sequelize models with `defaultFields`, make sure `DB_SESSION` or equivalent audit fields populate `created_by`, `created_date`, `updated_by`, and `updated_date`.

## Safe Errors And Logs

Return stable policy codes, not parser internals:

- `FILE_UPLOAD_INVALID`
- `FILE_TOO_LARGE`
- `FILE_TYPE_NOT_ALLOWED`
- `FILE_SCAN_FAILED`

Log allowed/blocked events with type, size, service/dirname, and code. Do not log original filenames, secrets, full tokens, or raw parser errors to client responses.

## Safe Negative Tests

After deployment, prove both allow and deny paths. Use synthetic files only:

- renamed script/executable bytes as `.png`: expect type rejection.
- corrupt image with valid magic header: expect type rejection.
- active-marker PDF with `/OpenAction` or `/JavaScript`: expect type rejection.
- XLSX containing `xl/vbaProject.bin`: expect type rejection.
- XLSX with `../evil.txt` ZIP entry: expect type rejection.
- ZIP bomb metadata pattern: expect size rejection.
- file larger than policy limit: expect size rejection.
- EICAR string: only when ClamAV is enabled; expect scan rejection.

For each blocked case, verify no DB row and no final disk object are created.

## Review Questions

- Is any helper under a routable `src/services` tree in old-core `qpay-micro-service` apps? Move pure helpers to `src/utils` or another non-routable location.
- Does the response prove new behavior, not old deployed code? UUID filename and corrected MIME are useful indicators.
- Are public reads intentionally unchanged? If yes, document compatibility as an ADR.
- Are ClamAV envs mapped through every `SERVER_ENV` config block?
- Are tests outside `src` if Babel build copies `src` into `dist`?

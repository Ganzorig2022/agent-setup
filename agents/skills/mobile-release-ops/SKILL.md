---
name: mobile-release-ops
description: Store-submission and mobile-credential operations for Expo/EAS apps — Google Play app signing and upload-key pinning, IARC content ratings, closed testing and the 12-tester production gate, tester opt-in links, Play submission service accounts, App Store version trains, APNs push keys, per-package EAS Android credentials, and Meta app publishing plus business verification. Use before any store submission, version bump, keystore or push-credential change, tester invite, or Meta app publish — and when a submit is rejected with a signing, version-train, or missing-data error.
---

# Mobile Release Ops

Hard-won, verified facts about shipping Expo/EAS apps to Google Play, the App Store, and Meta. Every item here was learned from a real failure — the traps are non-obvious and several are unrecoverable.

## Check these BEFORE building

A wasted build is the common failure mode. Before `eas build`:

1. **iOS**: is the app already live at this `expo.version`? If yes, bump it — see *App Store version trains*.
2. **Android**: is a keystore already pinned for this package? See *Play app signing*.
3. **Credentials are per-package** — a key existing in the EAS account proves nothing. See *EAS Android credentials*.

---

## Google Play — app signing and upload keys

Play **permanently pins** an app's upload key to the cert of the **first bundle ever uploaded**. A freshly generated keystore (e.g. EAS auto-generating one when it has no stored credentials) does **not** supersede it, and re-signing cannot fix it — the upload is simply rejected *"signed with the wrong key"*.

- `Request upload key reset` and `Change app signing key` are **developer-account-OWNER only**. App-level "Admin (all permissions)" does **not** grant them.
- An app with **no bundle ever uploaded** shows an empty "Upload key certificate" and accepts any keystore on its first upload.
- Console location moved (2026): Protected with Play → Play Store protection → *Manage Play app signing* = `/app/<id>/keymanagement`. The old `/app-integrity` redirects to the app list.

**Keep upload keystores backed up somewhere the team controls — losing one is unrecoverable without the account owner.**

### Backing up a keystore (interactive only)

`eas credentials` → Android → production → Keystore → *Download existing keystore*.

eas-cli has **no non-interactive mode at all** (verified 21.6.0: `eas credentials` accepts only `--platform` — no `--json`, no read subcommand), so credential state **cannot be audited programmatically**. Hand this step to the user.

Three traps on that path:

- The `.jks` lands **inside** `apps/<app>/` and is **not** gitignored. `MYAPP_UPLOAD_*` passwords are already committed in `apps/*/package.json` — both halves in one repo means anyone with repo access can sign the app.
- `git clean -fdx` deletes it, because it is untracked.
- Right after the download, the menu cursor rests on **"Set up a new keystore"** — selecting it mints a new key and reproduces the pinned-key dead end.

That same *Set up a new keystore → upload existing* path is the **correct way to restore** a recovered original keystore.

## Google Play — content ratings (IARC)

Completing the IARC questionnaire **is** accepting IARC's Terms of Use on the developer account's behalf, and it issues official public ratings. **Get explicit human sign-off before submitting it.**

Answer from **observed app behaviour, not intent**: an app rendering server-fetched catalogue or product data must answer **"Online content = Yes"** (Play's own example is Amazon product listings). Under-declaring is the rejection risk.

## Google Play — closed testing and the production gate

- Tester **"email lists" are account-level and shared across all apps**. Adding an address once propagates to every app and track using that list. Membership edits **never enter Google review** — review covers releases, store listing, and App content only.
- Opt-in progress toward the **12-tester / 14-day** production gate appears **only** on the app **Dashboard** → *Apply for access to production* (`/console/u/0/developers/<devId>/app/<appId>/app-dashboard`), as "N testers currently opted in".
- The app-list **"Installed audience" column is a lagged daily batch stat (24–48h) and is NOT the metric Google evaluates.** Reading it as progress is a false negative.
- The gate is **per-app**. Each app runs its own independent 12-tester/14-day clock, so one app clearing it says nothing about the others.
- **`internal`-track submissions are a separate track** that does not touch, reset, or advance the gate.

Console URLs need the developer ID (`/developers/<devId>/app/<appId>/…`); omitting it bounces to the account chooser. The publishing-overview slug is `/publishing`.

## Google Play — tester opt-in links

`play.google.com/apps/testing/<package>` gets **captured by the Play Store app** on Android — Samsung especially — which has no UI for that path and renders a **blank sheet titled "Google Play"**.

Testers must copy the link and paste it into a browser, or disable Settings → Apps → Google Play Store → *Open supported links*. **Put that instruction ABOVE the links in every tester invite.**

The `store/apps/details?id=` variant is worse: it only resolves after opt-in.

## Google Play — submission service account without owner access

Play Console **API access** is unavailable to non-owner accounts — absent from Settings entirely, and the `/api-access` slug redirects to the app list. **That does not block creating a working service account.**

**Users and permissions → Invite new users works for app-level admins.** Steps:

1. Create the SA in Google Cloud Console (any project you control); enable `androidpublisher.googleapis.com`.
2. Invite its `…iam.gserviceaccount.com` address with **App permissions** (`Release to testing tracks` + `Release to production…`), Account permissions empty.
3. Play grants ~6 permissions per app and marks it **Active immediately** — service accounts skip email confirmation.

**Verified end-to-end 2026-08-07:** the owner-only API-access GCP-project link is **not** required. `eas submit` succeeded on the first try (`Key Source: EAS servers`) with nothing but the Cloud Console SA plus the Users-and-permissions invite, on an account where the API access page is invisible.

Note manual AAB upload via the Play web UI needs no service account at all, so a missing one never blocks a release — only automation.

## App Store — version trains close on approval

Once a `CFBundleShortVersionString` is **approved**, Apple rejects every further upload under it:

```
90186  Invalid Pre-Release Train
90062  This bundle is invalid … must contain a higher version than the previously approved version
```

EAS `autoIncrement: true` + `appVersionSource: "remote"` bump only the **build number**, never the version string. So a production iOS build from an unchanged `app.json` is **dead on arrival** for any app already live at that version.

**Check the app's App Store release state and bump `expo.version` BEFORE building**, not after the submit fails — a rejected submit wastes the whole build.

Unaffected:

- Sandbox/preview ASC apps (separate app record, never approved). This is why preview uploads keep working while production fails.
- Android, which needs an increasing `versionCode`, not `versionName`.

Side effect: with `runtimeVersion: {policy: "appVersion"}`, a version bump also starts a **new EAS Update train**, so existing installs stay on the old OTA track until they update from the store.

## iOS push — orphaned APNs keys silently block all future setup

Apple caps team-scoped APNs auth keys (**2 by default**), and EAS names the ones it creates `Expo Push Notifications Key <timestamp>`.

If such a key is deleted from the EAS side (or the account is reset) **without being revoked at Apple**, it survives as an unusable orphan — the `.p8` is unrecoverable, since Apple only allows one download at creation.

**Symptom:** `eas credentials` reports *"There are no Push Keys available in your EAS account"* while Apple returns *"You have already reached the maximum allowed number of team scoped Keys for this service"*.

**Fix:** developer.apple.com → Certificates, Identifiers & Profiles → **Keys** (`/account/resources/authkeys/list`) → revoke the orphaned `Expo Push Notifications Key …` entries → re-run the generate path. Orphans are provably dead if EAS holds no key and the project has never delivered an iOS push.

APNs keys are **team-scoped**: one key serves every bundle ID (prod + preview, all apps). After the first `Set up your project to use Push Notifications`, always pick **"Use an existing push key"** — never generate again.

Assigning a key needs **no rebuild** — it lives on Expo's servers, so builds already in TestFlight start delivering immediately.

**Tokens are not evidence.** iOS mints an `ExponentPushToken` **without** any APNs key (only the entitlement is needed), so tokens accumulate in the DB while delivery silently fails. Check the Expo project's push count instead of the token rows.

## EAS — Android credentials are scoped per application identifier

The mirror image of team-scoped APNs keys. Both **FCM V1 push keys** and **Play-submission service-account keys** attach to **ONE `applicationId`** inside an EAS project — so a key existing in the EAS account says nothing about whether any given package is assigned.

**Audit every package separately**: `eas credentials --platform android`, once per build profile. The profile's `EXPO_PUBLIC_APP_VARIANT` is what selects the package. A 6-package sweep found **3 silently unassigned**, including a production app whose Android push had never worked.

- Prefer **"Select/Choose an existing key"**. "Upload a new service account key" mints a **duplicate EAS record** for identical key material.
- `eas.json` `submit.<profile>.android.serviceAccountKeyPath` **overrides** the EAS-stored key — leaving it in after uploading to EAS makes every submit fail on the missing local file. Delete it.
- Every app dir also contains a `google-services.json` (Firebase **client** config, not a credential) that a relative path grabs by mistake. EAS rejects it with *"you uploaded a google-services.json instead of your service account key"*. **Use absolute paths.**

## Meta — app publishing and business verification

A **business app** (Facebook Login for Business, Pages/IG/Messenger use cases) **cannot offer consumer login**. That needs a **second, dedicated login app** — so one frontend serving both needs **two env vars** (consumer login vs business Page-connect), or the Page-connect flow silently requests Page scopes from an app that has none.

For a login-only app **no App Review is needed** (`email` / `public_profile` are auto-granted). The Page/IG/Messenger app needs App Review on top.

### Verification is not the only Publish gate

The checklist also requires **App settings → Basic** complete, and Meta counts a leftover **placeholder as *missing*, not invalid**: `https://www.facebook.com/` (which Meta pre-fills) yields *"Currently ineligible for submission — your submission is missing data in the following fields"*.

**Audit Privacy policy / Terms of Service / User data deletion on every app** before assuming verification is the last step — the same placeholder was found sitting in two sibling apps in one portfolio.

`App settings` is a **separate collapsed group at the bottom of the left sidebar**; `Basic` does not exist as a target until you expand it. Direct URL: `developers.facebook.com/apps/<APP_ID>/settings/basic/`.

### Finding the verification wizard

It is **buried at the bottom of the left column of Security Center**, below the 2FA/Passkey cards. The "View details" links on Business info and on the app's Publish page **do** land on the right page, but above the fold — so it reads as a dead end. (`/business_verification/?business_id=` returns "content isn't available".)

Business details go **read-only** (`aria-disabled`) while verification is `In review`.

### Documents and language

**Mongolian is not among Meta's 21 supported document languages** → a stamped agency English translation is required, and Business details must then be entered in **Latin to match the translated document**, not Cyrillic.

When mailbox/phone access is missing, **Domain verification is the reliable connection method** — a domain already `Verified` under Business settings → Domains makes it instant, with no code or DNS.

### Console automation warning

Meta's Business/Developers console is hostile to automation: token/chip inputs (App domains, redirect URIs, JS SDK allowed domains) need `Return` to commit before Save, or the value is silently dropped on reload. Buttons often need a second click. **Always verify a save by reloading, never by absence of an error.**

---

## Related

- Demo/seed account credentials drift in production — verify with a real API login immediately before publishing them to an App Store demo account, tester handout, or docs. A stale one cost a Guideline 2.1 rejection and a month of review round-trips.
- Browser-driving these consoles: load the `chrome-devtools-axi` skill first.

# Frontend Bug Fixes Design

**Date:** 2026-03-27
**Scope:** ImageTo3D.jsx, ImageUploader.jsx, App.jsx

## Bug 1: Blob URL Leak in Error Path

**Location:** `ImageTo3D.jsx:101-110` (`handleRemoveBg`)

**Problem:** When `removeBackground()` returns a blob URL but the subsequent
`fetch(url)` or `response.blob()` throws, the URL is never stored in state
and never revoked. Each occurrence permanently leaks a blob URL.

**Fix:** Declare `url` outside the try block so the catch block can revoke it.

```jsx
let url
try {
  url = await removeBackground(...)
  // ...fetch blob, set state
} catch (err) {
  if (url) URL.revokeObjectURL(url)
  // ...existing error handling
}
```

## Bug 2: Race Condition — fetch(blobUrl) Without Abort Signal

**Location:** `ImageTo3D.jsx:106`

**Problem:** After `removeBackground` returns, `fetch(url)` executes without
the AbortController signal. If the user triggers a new removal during that
fetch, the old handler continues and can set stale state.

**Fix:** Pass the abort signal to the local fetch call.

```jsx
const response = await fetch(url, { signal: abortControllerRef.current.signal })
```

## Bug 3: Tab Switching Destroys In-Progress Work

**Location:** `App.jsx:35-37`

**Problem:** Conditional rendering with `&&` unmounts components when switching
tabs, losing all state (uploaded files, results, in-progress operations).

**Fix:** Replace conditional rendering with CSS `display: none` so all three
tab components stay mounted:

```jsx
<div style={{ display: activeTab === 'remove-bg' ? 'block' : 'none' }}>
  <ImageUploader />
</div>
<div style={{ display: activeTab === 'voice-clone' ? 'block' : 'none' }}>
  <VoiceCloner />
</div>
<div style={{ display: activeTab === 'image-to-3d' ? 'block' : 'none' }}>
  <ImageTo3D />
</div>
```

**Trade-off:** Three components live in DOM simultaneously. Memory impact is
negligible for this app.

## Bug 4: ImageUploader Missing Abort of Previous Request

**Location:** `ImageUploader.jsx:72` (`handleSubmit`)

**Problem:** Unlike `ImageTo3D.jsx`, `ImageUploader` does not abort the
previous request before creating a new AbortController. While the submit
button is disabled during loading (preventing UI-level double submission),
this is an inconsistent safety pattern.

**Fix:** Add `abortControllerRef.current?.abort()` before creating the new
controller.

```jsx
abortControllerRef.current?.abort()
abortControllerRef.current = new AbortController()
```

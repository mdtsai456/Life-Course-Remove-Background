# Frontend Bug Fixes Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix 4 frontend bugs: blob URL leak, race condition, tab state loss, and missing abort.

**Architecture:** Targeted edits to 3 files. No new dependencies, no new components. Bug 3 changes rendering strategy from conditional mount to CSS visibility.

**Tech Stack:** React 19, Vite 8

**Validation:** `npm run lint` and `npm run build` after each task. No test runner is configured in this project.

---

### Task 1: Fix blob URL leak in ImageTo3D error path

**Files:**
- Modify: `frontend/src/components/ImageTo3D.jsx:85-118`

**Step 1: Edit `handleRemoveBg` to track URL for cleanup**

Hoist `url` declaration out of `try` and revoke it in `catch` if the blob-fetch fails.

In `frontend/src/components/ImageTo3D.jsx`, replace the `handleRemoveBg` function (lines 85-118) with:

```jsx
  async function handleRemoveBg(e) {
    e.preventDefault()
    if (!file) return

    abortControllerRef.current?.abort()
    abortControllerRef.current = new AbortController()
    setStep('removing')
    setError('')
    setRemovedBgUrl(null)
    setRemovedBgBlob(null)
    setModel3dUrl(null)
    clearTimeout(removePhaseTimerRef.current)
    setRemovePhase('uploading')

    const uploadTimer = setTimeout(() => setRemovePhase('processing'), 800)
    let url
    try {
      url = await removeBackground(file, abortControllerRef.current.signal)
      clearTimeout(uploadTimer)
      setRemovePhase('done')
      removePhaseTimerRef.current = setTimeout(() => setRemovePhase(null), 500)
      // Also store as Blob for re-upload to /api/image-to-3d
      const response = await fetch(url, { signal: abortControllerRef.current.signal })
      const blob = await response.blob()
      setRemovedBgUrl(url)
      setRemovedBgBlob(blob)
      setStep('removed')
    } catch (err) {
      clearTimeout(uploadTimer)
      setRemovePhase(null)
      if (url) URL.revokeObjectURL(url)
      if (err.name === 'AbortError') return
      setError(err.message || 'Something went wrong. Please try again.')
      setStep('idle')
    }
  }
```

Changes from the original:
1. `let url` declared before `try` (was `const url` inside `try`)
2. `fetch(url, { signal: abortControllerRef.current.signal })` — adds abort signal (also fixes Bug 2)
3. `if (url) URL.revokeObjectURL(url)` in catch block — revokes leaked URL

**Step 2: Verify lint and build pass**

Run: `cd frontend && npm run lint && npm run build`
Expected: No errors.

**Step 3: Commit**

```bash
git add frontend/src/components/ImageTo3D.jsx
git commit -m "fix(ImageTo3D): revoke blob URL on error and add abort signal to fetch

Fixes two bugs in handleRemoveBg:
1. Blob URL leak: if fetch(blobUrl) threw after removeBackground
   returned, the URL was never revoked. Now caught and revoked.
2. Race condition: fetch(blobUrl) now uses the AbortController
   signal, preventing stale state from old requests."
```

---

### Task 2: (Completed in Task 1)

Bug 2 (race condition — `fetch` without abort signal) is fixed in Task 1 Step 1 by adding `{ signal: abortControllerRef.current.signal }` to the `fetch(url)` call. No additional work needed.

---

### Task 3: Preserve tab state with CSS display instead of conditional rendering

**Files:**
- Modify: `frontend/src/App.jsx:34-38`

**Step 1: Replace conditional rendering with CSS visibility**

In `frontend/src/App.jsx`, replace the `<main>` block (lines 34-38) with:

```jsx
      <main>
        <div style={{ display: activeTab === 'remove-bg' ? 'block' : 'none' }}>
          <ImageUploader />
        </div>
        <div style={{ display: activeTab === 'voice-clone' ? 'block' : 'none' }}>
          <VoiceCloner />
        </div>
        <div style={{ display: activeTab === 'image-to-3d' ? 'block' : 'none' }}>
          <ImageTo3D />
        </div>
      </main>
```

Changes from the original:
- Components are always mounted (never unmounted on tab switch)
- Inactive tabs are hidden with `display: none`
- All in-progress work, uploaded files, and results are preserved

**Step 2: Verify lint and build pass**

Run: `cd frontend && npm run lint && npm run build`
Expected: No errors.

**Step 3: Commit**

```bash
git add frontend/src/App.jsx
git commit -m "fix(App): preserve tab state with CSS display instead of unmounting

Tab components are now always mounted and hidden via display:none
when inactive. Previously, switching tabs would unmount the component,
losing all uploaded files, results, and in-progress operations."
```

---

### Task 4: Add missing abort of previous request in ImageUploader

**Files:**
- Modify: `frontend/src/components/ImageUploader.jsx:72`

**Step 1: Add abort call before creating new AbortController**

In `frontend/src/components/ImageUploader.jsx`, replace line 72:

```jsx
    abortControllerRef.current = new AbortController()
```

with:

```jsx
    abortControllerRef.current?.abort()
    abortControllerRef.current = new AbortController()
```

This matches the pattern already used in `ImageTo3D.jsx:89-90`.

**Step 2: Verify lint and build pass**

Run: `cd frontend && npm run lint && npm run build`
Expected: No errors.

**Step 3: Commit**

```bash
git add frontend/src/components/ImageUploader.jsx
git commit -m "fix(ImageUploader): abort previous request before creating new controller

Matches the safety pattern used in ImageTo3D.jsx. While the submit
button is disabled during loading, this ensures consistency and
prevents potential issues if the UI logic changes."
```

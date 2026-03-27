# Frontend Bug Fixes Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix 4 frontend bugs: blob URL leak, race condition, tab state loss, and missing abort.

**Architecture:** Targeted edits to 3 files. No new dependencies, no new components. Bug 3 changes rendering strategy from conditional mount to CSS visibility.

**Tech Stack:** React 19, Vite 8

**Validation:** `npm run lint` and `npm run build` after each task. No test runner is configured in this project.

---

## Tasks

### Task 1: Fix blob URL leak and abort race condition in ImageTo3D

**Files:**
- Modify: `frontend/src/components/ImageTo3D.jsx:104-142`

**Step 1: Edit `handleRemoveBg` with per-call locals to prevent race conditions**

Hoist `url` declaration out of `try`, use local controller and local timer variables so a stale catch can't clear a newer request's timer or mutate shared UI state.

In `frontend/src/components/ImageTo3D.jsx`, replace the `handleRemoveBg` function with:

```jsx
  async function handleRemoveBg(e) {
    e.preventDefault()
    if (!file) return

    abortControllerRef.current?.abort()
    const localController = new AbortController()
    abortControllerRef.current = localController
    setStep('removing')
    setError('')
    setRemovedBgUrl(null)
    setRemovedBgBlob(null)
    setModel3dUrl(null)
    clearTimeout(removePhaseTimerRef.current)
    setRemovePhase('uploading')

    const localUploadTimer = setTimeout(() => setRemovePhase('processing'), 800)
    uploadTimerRef.current = localUploadTimer
    let url
    try {
      url = await removeBackground(file, localController.signal)
      clearTimeout(localUploadTimer)
      if (localController.signal.aborted) return
      setRemovePhase('done')
      removePhaseTimerRef.current = setTimeout(() => setRemovePhase(null), 500)
      // Also store as Blob for re-upload to /api/image-to-3d
      const response = await fetch(url, { signal: localController.signal })
      const blob = await response.blob()
      setRemovedBgUrl(url)
      setRemovedBgBlob(blob)
      setStep('removed')
    } catch (err) {
      clearTimeout(localUploadTimer)
      if (url) URL.revokeObjectURL(url)
      if (err.name === 'AbortError' || localController.signal.aborted) return
      setRemovePhase(null)
      setError(err.message || 'Something went wrong. Please try again.')
      setStep('idle')
    }
  }
```

Apply identical pattern to `handleConvertTo3D`.

Changes from the original:
1. `const localController` — per-call controller prevents stale catch from mutating newer request's state
2. `const localUploadTimer` + `uploadTimerRef.current = localUploadTimer` — local for catch cleanup, ref for visibility/unmount cleanup
3. `if (localController.signal.aborted) return` — guard in try after await
4. `if (url) URL.revokeObjectURL(url)` in catch — revokes leaked URL
5. `fetch(url, { signal: localController.signal })` — abort signal on fetch (also fixes Bug 2)

**Step 2: Verify lint and build pass**

Run: `cd frontend && npm run lint && npm run build`
Expected: No errors.

**Step 3: Commit**

```bash
git add frontend/src/components/ImageTo3D.jsx
git commit -m "fix(ImageTo3D): revoke blob URL on error and fix abort race condition

Uses per-call local controller and timer variables so a stale
catch block cannot clear a newer request's timer or reset its
UI phase. Also revokes leaked blob URL on error."
```

---

### Task 2: (Completed in Task 1)

Bug 2 (race condition — `fetch` without abort signal) is fixed in Task 1 Step 1 by adding `{ signal: localController.signal }` to the `fetch(url)` call. No additional work needed.

---

### Task 3: Preserve tab state with CSS display instead of conditional rendering

**Files:**
- Modify: `frontend/src/App.jsx:34-38`

**Step 1: Replace conditional rendering with CSS visibility**

In `frontend/src/App.jsx`, replace the `<main>` block (lines 34-38) with:

```jsx
      <main>
        <div style={{ display: activeTab === 'remove-bg' ? 'block' : 'none' }}>
          <ImageUploader visible={activeTab === 'remove-bg'} />
        </div>
        <div style={{ display: activeTab === 'voice-clone' ? 'block' : 'none' }}>
          <VoiceCloner visible={activeTab === 'voice-clone'} />
        </div>
        <div style={{ display: activeTab === 'image-to-3d' ? 'block' : 'none' }}>
          <ImageTo3D visible={activeTab === 'image-to-3d'} />
        </div>
      </main>
```

Changes from the original:
- Components are always mounted (never unmounted on tab switch)
- Inactive tabs are hidden with `display: none`
- `visible` prop passed to each component so they can abort in-flight requests and reset loading state when hidden
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

### Task 4: Add missing abort of previous request in ImageUploader (Done)

**Status: Already implemented in code.**

`frontend/src/components/ImageUploader.jsx:81` already has:
```jsx
    abortControllerRef.current?.abort()
    const localController = new AbortController()
    abortControllerRef.current = localController
```

No additional work needed.

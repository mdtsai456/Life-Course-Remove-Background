---
title: "feat: Add drag & drop and paste image upload"
type: feat
status: completed
date: 2026-03-27
origin: docs/brainstorms/2026-03-27-drag-drop-paste-requirements.md
---

# feat: Add drag & drop and paste image upload

## Overview

Extend `ImageUploader` to accept images via drag & drop and Ctrl+V/Cmd+V paste, in addition to the existing file picker. All three entry points share the same validation logic and state path.

## Problem Frame

`ImageUploader` currently only supports file picker selection. Users expect to drag an image from the desktop or another browser tab, or paste a screenshot from the clipboard. The gap makes the UI feel unnecessarily limited. (see origin: docs/brainstorms/2026-03-27-drag-drop-paste-requirements.md)

## Requirements Trace

- R1. Drag & drop an image onto the upload area to select it
- R2. Visual feedback (border highlight) while dragging over the drop zone
- R3. Ctrl+V / Cmd+V paste from clipboard to select an image
- R4. Drop and paste inputs pass through the same validation as file picker (type + size)
- R5. Invalid drop/paste shows the same error messages as invalid file picker selection
- R6. Paste listener is only active when the `ImageUploader` tab is visible

## Scope Boundaries

- No multi-file / batch support — only the first file from a drop or paste is used
- Non-image drag types (text, URLs, links) are silently ignored
- No backend changes

## Context & Research

### Relevant Code and Patterns

- `frontend/src/components/ImageUploader.jsx` — target component; `handleFileChange` (lines 52-75) contains the validation logic to extract into a shared helper
- `frontend/src/components/VoiceCloner.jsx` — canonical example of a `useEffect` with `[visible]` dependency that adds/removes a `window`-level event listener; the paste listener must follow the same pattern
- `frontend/src/index.css` — all styles live here; the drag-over class must be added here (no component-scoped CSS in this repo)
- `App.jsx` — tabs use `display: none` toggling (not unmounting); `visible` prop is the canonical "tab is active" signal

### Institutional Learnings

- No `docs/solutions/` directory exists; no prior learnings available.

### External References

- Not required — web standards for drag & drop and clipboard paste are well-established; repo research provided sufficient concrete guidance.

## Key Technical Decisions

- **Extract `applyFile(file)` helper**: Pull the validation + state-setting block out of `handleFileChange` into a standalone `applyFile` function called by all three entry points (file picker, drag & drop, paste). Avoids duplicating validation logic. (see origin: Key Decisions)
- **Drop zone target is `.uploader` div**: The outermost wrapper already exists; no new wrapper element needed.
- **Drag counter ref for dragenter/dragleave**: Use a `dragCounterRef = useRef(0)` to track nested `dragenter`/`dragleave` events. Increment on `dragenter`, decrement on `dragleave`; set `isDragOver` based on `counter > 0`. This prevents the flicker caused by child elements firing `dragleave` when the cursor moves over them — a known browser behaviour with no simpler fix.
- **Paste listener on `window` with `[visible]` dependency**: When `visible` becomes false, the `useEffect` cleanup removes the listener. Mirrors the `VoiceCloner` pattern exactly. (see origin: Key Decisions)
- **`isDragOver` as `useState(false)`**: Purely presentational; drives a CSS class toggle on `.uploader`. Consistent with how other boolean UI state is handled in the component.
- **CSS class toggle via new `.drag-over` modifier**: Added to `index.css` to match repo convention (no inline style objects for component state). Use the existing blue `#2563eb` accent colour to signal an active drop target.

## Open Questions

### Resolved During Planning

- **Drop zone target**: `.uploader` div — confirmed as the outermost wrapper; no structural change required.
- **Drag feedback approach**: CSS class toggle via `isDragOver` state + new `.drag-over` modifier in `index.css` — matches repo convention (all styles in `index.css`, no inline style objects).
- **Paste compatibility**: `ClipboardEvent.clipboardData.items` with `item.kind === 'file'` and `item.getAsFile()` is supported in all modern browsers (Chrome, Firefox, Safari, Edge). No polyfill needed for this project's target audience.

### Deferred to Implementation

- **Exact CSS values for `.drag-over`**: Border colour, background tint, and transition — to be decided when the implementer can see the visual result against the existing design.

## Implementation Units

- [x] **Unit 1: Refactor validation + add drag & drop**

  **Goal:** Extract file validation into `applyFile`, add drag & drop handlers to `.uploader`, add `isDragOver` state and drag counter ref.

  **Requirements:** R1, R2, R4, R5

  **Dependencies:** None

  **Files:**
  - Modify: `frontend/src/components/ImageUploader.jsx`
  - Test: No frontend test suite exists in this repo; verify manually per test scenarios below.

  **Approach:**
  - Extract the body of `handleFileChange` (type check, size check, `setError`, `setFile`) into a new `applyFile(file)` function defined inside the component.
  - `handleFileChange` becomes a one-liner that calls `applyFile(e.target.files?.[0] ?? null)`.
  - Add `const [isDragOver, setIsDragOver] = useState(false)` and `const dragCounterRef = useRef(0)`.
  - Add four handlers on the `.uploader` div:
    - `onDragEnter`: `e.preventDefault(); dragCounterRef.current++; setIsDragOver(true)`
    - `onDragOver`: `e.preventDefault()` (required to allow drop; no state change)
    - `onDragLeave`: `dragCounterRef.current--; if (dragCounterRef.current === 0) setIsDragOver(false)`
    - `onDrop`: `e.preventDefault(); dragCounterRef.current = 0; setIsDragOver(false); applyFile(e.dataTransfer.files[0] ?? null)`
  - Apply `drag-over` CSS class to `.uploader` when `isDragOver` is true: `className={\`uploader\${isDragOver ? ' drag-over' : ''}\`}`

  **Patterns to follow:**
  - `handleFileChange` in `ImageUploader.jsx` (lines 52-75) for validation logic
  - `isDragOver` boolean state follows the same `useState` + className toggle pattern used for `loading`

  **Test scenarios:**
  - Drag a valid PNG over the upload area → border highlights while hovering, clears on release
  - Drop a valid JPEG → original image preview appears, no error
  - Drop a file with unsupported type (e.g. `.gif`) → error message appears, no preview
  - Drop a file exceeding 10 MB → size error message appears
  - Drag in, then drag back out without dropping → highlight clears, no error
  - Drag a child element within `.uploader` → no flicker on drag-over highlight (counter fix)
  - Drop while a previous upload is in progress → existing abort logic handles it correctly (no change needed)

  **Verification:**
  - All three entry points (file picker, drag & drop) call the same validation path
  - `dragCounterRef` correctly reaches 0 when cursor leaves the drop zone, even via child elements
  - `isDragOver` is false after a drop or after dragging out

- [x] **Unit 2: Add paste listener**

  **Goal:** Register a `window` paste listener that feeds the first image item from the clipboard through `applyFile`.

  **Requirements:** R3, R4, R5, R6

  **Dependencies:** Unit 1 (requires `applyFile` to exist)

  **Files:**
  - Modify: `frontend/src/components/ImageUploader.jsx`

  **Approach:**
  - Add a `useEffect` with `[visible]` dependency.
  - When `visible` is true: define `handlePaste(e)` that iterates `e.clipboardData.items`, finds the first item where `item.kind === 'file'` and `ALLOWED_TYPES.includes(item.type)`, calls `item.getAsFile()`, and passes the result to `applyFile`. If no image item is found, do nothing (silently ignore non-image pastes).
  - Register with `window.addEventListener('paste', handlePaste)` and return a cleanup that calls `window.removeEventListener('paste', handlePaste)`.
  - When `visible` is false: the effect returns without registering (or the cleanup from the previous run removes it).
  - `clipboardData.items` must be accessed synchronously inside the `paste` handler — do not defer to a Promise or async path.

  **Patterns to follow:**
  - `VoiceCloner.jsx` window-level listener with `[visible]` dependency — exact structural mirror

  **Test scenarios:**
  - Paste a PNG screenshot while on the Remove Background tab → image appears in the file picker preview, submit becomes enabled
  - Paste a JPEG from the clipboard → same as above
  - Paste non-image content (text, a URL) → nothing happens, no error
  - Switch to another tab, paste an image → listener is not active, `ImageUploader` is unaffected
  - Paste while a previous upload is in progress → `applyFile` resets result and error, sets new file; existing abort happens on submit, not on file selection

  **Verification:**
  - Listener is registered exactly once when `visible` becomes true
  - Listener is removed when `visible` becomes false or component unmounts
  - No duplicate handlers when the user switches tabs back and forth repeatedly

- [x] **Unit 3: CSS drag-over visual feedback**

  **Goal:** Add a `.drag-over` modifier class to `index.css` that highlights the upload area while a file is being dragged over it.

  **Requirements:** R2

  **Dependencies:** Unit 1 (establishes which element receives the class)

  **Files:**
  - Modify: `frontend/src/index.css`

  **Approach:**
  - Add a `.uploader.drag-over` rule (or `.uploader .drag-over` on a child if Unit 1 uses a child element — follow whichever approach Unit 1 took).
  - Style should signal "this is a valid drop target": a dashed or solid border in the existing `#2563eb` blue accent, a light background tint (`#eff6ff` or similar), and a smooth `transition` (e.g. `0.15s ease`).
  - Keep the rule minimal; do not introduce new layout or spacing.

  **Patterns to follow:**
  - Existing `.file-button` and `.submit-button` use `#2563eb` blue for interactive state
  - `border-radius: 8px` is the standard radius for card-like containers in this stylesheet
  - Transitions use `0.15s` duration elsewhere in the file

  **Test scenarios:**
  - Drag a file over the upload area → highlighted border and/or background tint appears
  - Move cursor off the area → styles reset to default immediately
  - Visual style does not break layout or shift content

  **Verification:**
  - Drag-over state is visually distinguishable from the default state
  - No layout shift when the class is applied or removed

## System-Wide Impact

- **Interaction graph:** Only `ImageUploader.jsx` is modified. `App.jsx`, `api.js`, and backend routes are untouched.
- **Error propagation:** No change — `applyFile` calls `setError` directly, same as before.
- **State lifecycle risks:** `dragCounterRef` must be reset to `0` on `onDrop` and `onDragLeave` reaching zero; if not reset, a subsequent drag session starts with a stale counter. Also reset in the `visible=false` cleanup effect to avoid stuck drag state when switching tabs mid-drag.
- **API surface parity:** Not applicable — no API changes.
- **Integration coverage:** The `visible` prop + `useEffect` cleanup pattern is already exercised by the existing tab-switching test path.

## Risks & Dependencies

- **Dragenter/dragleave child-element flicker**: Mitigated by `dragCounterRef`. Implementation must correctly reset the counter to `0` on `drop` and when counter reaches `0` on `dragleave` — a common source of stuck drag-over state.
- **Paste fires on wrong tab**: Mitigated by the `[visible]` guard in Unit 2. The listener is never registered when the tab is hidden.
- **`applyFile` refactor regression**: Extracting `handleFileChange`'s body must not change observable behaviour for the existing file picker path. The refactor is mechanical (extract function, replace inline code with a call), but should be verified against the existing file picker test scenarios.

## Sources & References

- **Origin document:** [docs/brainstorms/2026-03-27-drag-drop-paste-requirements.md](docs/brainstorms/2026-03-27-drag-drop-paste-requirements.md)
- Related code: `frontend/src/components/ImageUploader.jsx`, `frontend/src/components/VoiceCloner.jsx`, `frontend/src/index.css`

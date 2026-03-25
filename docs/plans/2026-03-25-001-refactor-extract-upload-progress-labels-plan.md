---
title: "refactor: Extract inline labels object to top-level constant in ImageUploader"
type: refactor
status: completed
date: 2026-03-25
---

# refactor: Extract inline labels object to top-level constant in ImageUploader

## Overview

Extract the inline `labels` object passed to `<ProgressStatus>` in `ImageUploader.jsx` into a module-level constant to prevent a new object reference on every render.

## Problem Frame

Line 126 of `ImageUploader.jsx` passes `labels={{ uploading: '上傳圖片中...', processing: '移除背景中...' }}` as an inline object literal. This creates a new object reference each render, which can cause unnecessary re-renders of `ProgressStatus` (relevant if it uses `React.memo` or `PureComponent`). The file already declares top-level constants (`MAX_FILE_SIZE`, `ALLOWED_TYPES`) so extracting follows established convention.

## Requirements Trace

- R1. Move the `labels` object outside the component so it is not recreated every render
- R2. Follow the existing top-level constant pattern in the file

## Scope Boundaries

- No behavioral change — output remains identical
- No changes to `ProgressStatus` component

## Context & Research

### Relevant Code and Patterns

- `frontend/src/components/ImageUploader.jsx` lines 5-6: existing top-level constants `MAX_FILE_SIZE` and `ALLOWED_TYPES`
- `frontend/src/components/ProgressStatus.jsx`: consumer of the `labels` prop

## Key Technical Decisions

- **Constant name `UPLOAD_PROGRESS_LABELS`**: Matches the SCREAMING_SNAKE convention of the sibling constants and clearly describes its purpose.
- **Placement after line 6**: Directly below `ALLOWED_TYPES` to keep all module constants grouped together.

## Implementation Units

- [ ] **Unit 1: Extract labels to top-level constant**

**Goal:** Replace inline object with a stable reference

**Requirements:** R1, R2

**Dependencies:** None

**Files:**
- Modify: `frontend/src/components/ImageUploader.jsx`

**Approach:**
- Declare `const UPLOAD_PROGRESS_LABELS = { uploading: '上傳圖片中...', processing: '移除背景中...' }` after line 6
- Replace the inline object on line 126 with `labels={UPLOAD_PROGRESS_LABELS}`

**Patterns to follow:**
- `MAX_FILE_SIZE` and `ALLOWED_TYPES` constant declarations at lines 5-6

**Verification:**
- `ProgressStatus` receives the same label values as before
- No new object created inside the component body
- App renders identically

#!/usr/bin/env node
// Wires quartz/ (the Quartz submodule) up to this repo's config and content
// via symlink, falling back to a copy when the platform refuses the symlink.
//
// Windows requires either Administrator privileges or Developer Mode enabled
// to create NTFS symbolic links (SeCreateSymbolicLinkPrivilege); without
// either, Node's fs.symlinkSync throws EPERM (Issue #273). Directory
// junctions ('junction' type) are a separate NTFS reparse-point mechanism
// that does NOT require that privilege, so quartz/content (a directory) uses
// it and normally succeeds even on a stock Windows install; quartz/
// quartz.config.yaml is a *file*, and junctions only work on directories, so
// it has no such unprivileged option and falls back to a plain copy on
// EPERM. On non-Windows platforms the 'junction' type argument is silently
// ignored (Node only honors it on win32), so this is a no-op behavior change
// there — a plain symlink is created as before.
//
// A copy fallback means quartz/content stops tracking live edits to
// content/; that's fine here because `npm run build`/`preview` always re-run
// `convert` (which fully regenerates content/, including Issue #271's stale
// cleanup) and then this script before invoking Quartz, so the copy is
// always fresh for that build.

const fs = require("fs");
const path = require("path");

function linkOrCopy(target, dest, isDir) {
  fs.rmSync(dest, { recursive: true, force: true });
  try {
    fs.symlinkSync(target, dest, isDir ? "junction" : "file");
  } catch (err) {
    if (err.code !== "EPERM") throw err;
    const resolvedTarget = path.resolve(path.dirname(dest), target);
    if (isDir) {
      fs.cpSync(resolvedTarget, dest, { recursive: true });
    } else {
      fs.copyFileSync(resolvedTarget, dest);
    }
  }
}

linkOrCopy("../quartz.config.yaml", path.join("quartz", "quartz.config.yaml"), false);
linkOrCopy("../content", path.join("quartz", "content"), true);

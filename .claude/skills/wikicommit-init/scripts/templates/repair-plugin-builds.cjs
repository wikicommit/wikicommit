#!/usr/bin/env node
// Repairs `npm run install-plugins`'s one-way stuck state (Issue #382).
//
// Quartz's own installer (quartz/quartz/cli/plugin-git-handlers.js,
// handlePluginInstallUnified) writes a plugin's quartz.lock.json entry as soon as
// `git clone` succeeds, *before* the plugin's own build step
// (`npm install --ignore-scripts && npm run build`, run inside the plugin's own
// directory) runs. If that build step fails — dependency resolution, a compile
// error, anything — Quartz swallows the exception and only increments an internal
// counter; the lockfile entry written at clone time is never corrected. The next
// `npx quartz plugin install --from-config` run's "already installed?" check is
// `lockfile.plugins[name] && fs.existsSync(pluginDir)`, which is still true (only
// the build failed, not the clone), so the broken plugin is silently skipped
// forever — unlike a clone failure, which never writes a lockfile entry at all and
// so is retried automatically on the next run. `npx quartz plugin install` itself
// never surfaces this as a non-zero exit code either (the CLI command handler
// just awaits the installer and returns), so a plain `&&`-chained npm script can't
// detect it from the exit status.
//
// This restores that self-healing behavior without touching the Quartz submodule:
// for every plugin recorded in quartz.lock.json whose directory was cloned but has
// no dist/ (the same completion signal Quartz's own hasPrebuiltDist/needsBuild use
// internally), delete the plugin's directory and lockfile entry so it looks
// "never installed" again, then re-run `npx quartz plugin install --from-config`
// so Quartz retries clone+build for it exactly as it already does for clone
// failures. Bounded retries handle transient failures (e.g. a flaky network
// during the clone-then-rebuild); a plugin still stuck after that many attempts
// gets a clear, actionable error instead of silently vanishing into the lockfile.

const fs = require("fs");
const path = require("path");
const { execSync } = require("child_process");

const QUARTZ_DIR = "quartz";
const LOCKFILE_PATH = path.join(QUARTZ_DIR, "quartz.lock.json");
const PLUGINS_DIR = path.join(QUARTZ_DIR, ".quartz", "plugins");
const MAX_ATTEMPTS = 3;

function readLockfile() {
  if (!fs.existsSync(LOCKFILE_PATH)) return null;
  try {
    return JSON.parse(fs.readFileSync(LOCKFILE_PATH, "utf-8"));
  } catch {
    return null;
  }
}

function writeLockfile(lockfile) {
  fs.writeFileSync(LOCKFILE_PATH, JSON.stringify(lockfile, null, 2) + "\n");
}

// A plugin is "stuck" when Quartz cloned it (lockfile entry + directory both
// exist) but never produced a dist/ — the same signal Quartz's own
// hasPrebuiltDist/needsBuild use to decide whether a plugin still needs building.
function findStuckPlugins(lockfile) {
  if (!lockfile || !lockfile.plugins) return [];
  return Object.keys(lockfile.plugins).filter((name) => {
    const pluginDir = path.join(PLUGINS_DIR, name);
    if (!fs.existsSync(pluginDir)) return false;
    return !fs.existsSync(path.join(pluginDir, "dist"));
  });
}

function clearStuckPlugins(lockfile, names) {
  for (const name of names) {
    fs.rmSync(path.join(PLUGINS_DIR, name), { recursive: true, force: true });
    delete lockfile.plugins[name];
  }
  writeLockfile(lockfile);
}

function hasDist(name) {
  return fs.existsSync(path.join(PLUGINS_DIR, name, "dist"));
}

function main() {
  // Every plugin ever seen stuck across all attempts — not just the last one. A
  // plugin we clear can, on retry, either recover (dist/ appears) or fail the
  // re-clone entirely (no directory at all, which findStuckPlugins doesn't count
  // as "stuck" since that's ordinarily a self-healing clone failure). Without
  // this set, that second case would make the plugin vanish from the final
  // check below and get reported as fixed when it's actually just as broken —
  // now completely missing instead of merely unbuilt.
  const everStuck = new Set();

  for (let attempt = 1; attempt <= MAX_ATTEMPTS; attempt++) {
    const lockfile = readLockfile();
    const stuck = findStuckPlugins(lockfile);
    if (stuck.length === 0) break;
    for (const name of stuck) everStuck.add(name);

    console.log(
      `repair-plugin-builds: ${stuck.length} plugin(s) cloned but never built successfully ` +
        `(attempt ${attempt}/${MAX_ATTEMPTS}): ${stuck.join(", ")}`,
    );
    clearStuckPlugins(lockfile, stuck);

    try {
      execSync("npx quartz plugin install --from-config", { cwd: QUARTZ_DIR, stdio: "inherit" });
    } catch {
      // Non-zero exit here doesn't necessarily mean nothing was fixed (other
      // plugins may have installed fine) — re-check dist/ below rather than
      // trusting this exit code either way.
    }
  }

  const stillBroken = [...everStuck].filter((name) => !hasDist(name));
  if (stillBroken.length > 0) {
    console.error(
      `repair-plugin-builds: ${stillBroken.length} plugin(s) still failed to build after ` +
        `${MAX_ATTEMPTS} attempts: ${stillBroken.join(", ")}`,
    );
    console.error(
      "This is likely a real build failure, not a transient one. To see the underlying error, run:",
    );
    for (const name of stillBroken) {
      console.error(`  cd ${path.join(PLUGINS_DIR, name)} && npm install --ignore-scripts && npm run build`);
    }
    process.exitCode = 1;
  }
}

main();

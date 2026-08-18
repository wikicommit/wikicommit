#!/usr/bin/env node
// Installs dependencies for every local Quartz plugin under quartz-plugins/
// (Issue #426).
//
// quartz.config.yaml references quartz-plugins/<name> by relative path, not
// by npm package name — these directories are never connected to an npm
// workspace and each carries its own package.json/package-lock.json. Before
// this script existed, nothing in the install flow ever ran `npm install`
// inside them: the root postinstall only installs quartz/ (the submodule),
// and install-plugins (`npx quartz plugin install --from-config` +
// repair-plugin-builds.cjs) only clones/builds *external* github: plugins.
// A fresh clone or devcontainer rebuild therefore left every quartz-plugins/*
// node_modules/ empty (gitignored, so never checked in), and Quartz silently
// dropped each plugin's components at build time ("declares components but
// failed to load them") without failing the build.
//
// Plugin directories are discovered dynamically (readdirSync + a
// package.json check), not hardcoded by name — same pattern
// .github/workflows/test.yml already uses (Issue #235) — so a newly added
// plugin directory is picked up automatically.

const fs = require("fs");
const path = require("path");
const { execSync } = require("child_process");

const PLUGINS_DIR = "quartz-plugins";

function findPluginDirs() {
  if (!fs.existsSync(PLUGINS_DIR)) return [];
  return fs
    .readdirSync(PLUGINS_DIR, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .map((entry) => path.join(PLUGINS_DIR, entry.name))
    // quartz-plugins/_shared/ (Issue #379) is a shared tsup config module,
    // not an installable plugin package — it has no package.json.
    .filter((dir) => fs.existsSync(path.join(dir, "package.json")))
    .sort();
}

function main() {
  const pluginDirs = findPluginDirs();
  if (pluginDirs.length === 0) {
    return;
  }

  const failed = [];
  for (const dir of pluginDirs) {
    console.log(`install-local-plugins: npm install in ${dir}`);
    try {
      execSync("npm install", { cwd: dir, stdio: "inherit" });
    } catch {
      failed.push(dir);
    }
  }

  if (failed.length > 0) {
    console.error(
      `install-local-plugins: ${failed.length} plugin(s) failed to install: ${failed.join(", ")}`,
    );
    process.exitCode = 1;
  }
}

main();

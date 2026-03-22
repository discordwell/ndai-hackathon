import * as esbuild from "esbuild";
import { execSync } from "child_process";
import { createHash } from "crypto";
import fs from "fs";
import path from "path";

const isWatch = process.argv.includes("--watch");

// Build Tailwind CSS
function buildCSS() {
  execSync(
    "npx tailwindcss -i ./src/styles.css -o ./dist/assets/styles.css --minify",
    { stdio: "inherit" }
  );
}

// Copy index.html to dist
function copyHTML() {
  const distDir = path.resolve("dist");
  if (!fs.existsSync(distDir)) fs.mkdirSync(distDir, { recursive: true });
  fs.copyFileSync(
    path.resolve("public/index.html"),
    path.resolve("dist/index.html")
  );
}

// Stub Node.js built-ins for browser (argon2-browser's Emscripten references fs/path)
const nodeStubPlugin = {
  name: "node-builtins-stub",
  setup(build) {
    build.onResolve({ filter: /^(fs|path|crypto)$/ }, (args) => ({
      path: args.path,
      namespace: "node-stub",
    }));
    build.onLoad({ filter: /.*/, namespace: "node-stub" }, () => ({
      contents: "module.exports = {};",
    }));
  },
};

const buildOptions = {
  entryPoints: ["src/main.tsx"],
  bundle: true,
  minify: !isWatch,
  sourcemap: isWatch,
  outdir: "dist/assets",
  format: "esm",
  splitting: true,
  target: ["es2020"],
  loader: {
    ".tsx": "tsx",
    ".ts": "ts",
    ".wasm": "file",
  },
  define: {
    "process.env.NODE_ENV": isWatch ? '"development"' : '"production"',
    "global": "globalThis",
  },
  plugins: [nodeStubPlugin],
};

if (isWatch) {
  const ctx = await esbuild.context(buildOptions);
  buildCSS();
  copyHTML();
  await ctx.watch();
  console.log("Watching for changes...");
} else {
  await esbuild.build(buildOptions);
  buildCSS();
  copyHTML();

  // Generate integrity.json — SHA-256 hashes of output bundles
  const assetsDir = path.resolve("dist/assets");
  const integrity = { build_timestamp: new Date().toISOString() };
  for (const file of fs.readdirSync(assetsDir)) {
    if (file.endsWith(".js") || file.endsWith(".css")) {
      const content = fs.readFileSync(path.join(assetsDir, file));
      integrity[file] = "sha256-" + createHash("sha256").update(content).digest("hex");
    }
  }
  fs.writeFileSync(path.join(assetsDir, "integrity.json"), JSON.stringify(integrity, null, 2));
  console.log("Build complete. Integrity hashes written.");
}

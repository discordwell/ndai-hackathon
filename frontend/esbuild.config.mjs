import * as esbuild from "esbuild";
import { execSync } from "child_process";
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
  },
  define: {
    "process.env.NODE_ENV": isWatch ? '"development"' : '"production"',
  },
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
  console.log("Build complete.");
}

#!/usr/bin/env node
// Validate ubersicht/cc-usage.jsx by transpiling it with Übersicht's OWN bundled
// @babel/preset-react — the same compiler the widget uses at runtime. If this
// passes, the JSX is syntactically valid and won't red-splash the load-bearing
// widget. ALWAYS run before installing a widget edit:
//   node scripts/jsxcheck.js ubersicht/cc-usage.jsx
const UB = "/Applications/Übersicht.app/Contents/Resources/node_modules";
const babel = require(UB + "/@babel/core");
const fs = require("fs");
const file = process.argv[2] || "ubersicht/cc-usage.jsx";
try {
  babel.transformSync(fs.readFileSync(file, "utf8"), {
    presets: [UB + "/@babel/preset-react"],
    filename: file,
  });
  console.log("✓ JSX VALID:", file);
} catch (e) {
  console.log("✗ JSX ERROR:", e.message.split("\n")[0]);
  process.exit(1);
}

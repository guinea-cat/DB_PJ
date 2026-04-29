import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { compileScript, compileTemplate, parse } from "@vue/compiler-sfc";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const appVuePath = path.resolve(__dirname, "../src/App.vue");

const source = fs.readFileSync(appVuePath, "utf8");
const { descriptor, errors } = parse(source, { filename: appVuePath });

if (errors.length) {
  console.error("SFC parse failed:");
  for (const error of errors) {
    if (typeof error === "string") {
      console.error(`- ${error}`);
      continue;
    }
    console.error(`- ${error.message}`);
  }
  process.exit(1);
}

let bindings = {};

try {
  const compiledScript = compileScript(descriptor, {
    id: "app-vue-check"
  });
  bindings = compiledScript.bindings;
} catch (error) {
  console.error("Script compile failed:");
  console.error(error.message);
  process.exit(1);
}

try {
  const templateResult = compileTemplate({
    id: "app-vue-check",
    filename: appVuePath,
    source: descriptor.template?.content || "",
    compilerOptions: {
      bindingMetadata: bindings
    }
  });

  if (templateResult.errors.length) {
    console.error("Template compile failed:");
    for (const error of templateResult.errors) {
      if (typeof error === "string") {
        console.error(`- ${error}`);
        continue;
      }
      console.error(`- ${error.message}`);
    }
    process.exit(1);
  }
} catch (error) {
  console.error("Template compile failed:");
  console.error(error.message);
  process.exit(1);
}

console.log("App.vue parsed and compiled successfully.");

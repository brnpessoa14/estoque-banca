import { copyFile, mkdir, rm } from "node:fs/promises";

const output = new URL("./public/", import.meta.url);
await rm(output, { recursive: true, force: true });
await mkdir(output, { recursive: true });

for (const filename of ["index.html", "styles.css", "app.js"]) {
  await copyFile(new URL(`./${filename}`, import.meta.url), new URL(filename, output));
}

console.log("Frontend preparado em public/.");

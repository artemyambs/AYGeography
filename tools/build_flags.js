const fs = require("fs");
const path = require("path");
const { Canvas, loadImage } = require("skia-canvas");

const root = path.resolve(__dirname, "..");
const source = path.join(root, "assets", "flags");
const output = path.join(root, "assets", "flags_png");
fs.mkdirSync(output, { recursive: true });

async function main() {
  const files = fs.readdirSync(source).filter((name) => name.toLowerCase().endsWith(".svg"));
  await Promise.all(files.map(async (name) => {
    const image = await loadImage(path.join(source, name));
    const canvas = new Canvas(360, 240);
    canvas.getContext("2d").drawImage(image, 0, 0, 360, 240);
    await canvas.saveAs(path.join(output, path.basename(name, path.extname(name)) + ".png"));
  }));
  process.stdout.write(`Built ${files.length} flag images\n`);
}

main().catch((error) => {
  process.stderr.write(String(error));
  process.exit(1);
});

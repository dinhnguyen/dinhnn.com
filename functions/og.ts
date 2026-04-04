export const onRequest: PagesFunction = async ({ request }) => {
  const { searchParams } = new URL(request.url);
  const title = searchParams.get("title") ?? "Định Nguyễn";

  return new Response(generateOgImage(title), {
    headers: {
      "Content-Type": "image/svg+xml",
      "Cache-Control": "public, max-age=86400, s-maxage=86400",
    },
  });
};

function escapeXml(str: string): string {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

function wrapText(text: string, maxChars: number): string[] {
  const words = text.split(" ");
  const lines: string[] = [];
  let line = "";
  for (const word of words) {
    if (line.length + word.length + 1 > maxChars) {
      if (line) lines.push(line);
      line = word;
    } else {
      line = line ? `${line} ${word}` : word;
    }
  }
  if (line) lines.push(line);
  return lines;
}

function generateOgImage(title: string): string {
  const lines = wrapText(escapeXml(title), 32);
  const lineHeight = 82;
  const startY = Math.max(180, 315 - ((lines.length - 1) * lineHeight) / 2);

  const textLines = lines
    .map(
      (line, i) =>
        `<text x="80" y="${startY + i * lineHeight}" fill="white" font-size="64" font-weight="300" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif" letter-spacing="-1">${line}</text>`
    )
    .join("\n  ");

  return `<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#0d2137"/>
      <stop offset="100%" stop-color="#0a4040"/>
    </linearGradient>
    <linearGradient id="accent" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="#3ecfcf"/>
      <stop offset="100%" stop-color="#1a8a8a"/>
    </linearGradient>
  </defs>
  <rect width="1200" height="630" fill="url(#bg)"/>
  <rect x="80" y="80" width="60" height="4" fill="url(#accent)" rx="2"/>
  ${textLines}
  <text x="1120" y="580" fill="rgba(255,255,255,0.4)" font-size="24" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif" text-anchor="end">dinhnn.com</text>
</svg>`;
}

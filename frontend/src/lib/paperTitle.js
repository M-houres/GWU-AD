function stripExtension(filename) {
  return String(filename || "").replace(/\.[^.]+$/, "")
}

function normalizeWhitespace(value) {
  return String(value || "").replace(/[_-]+/g, " ").replace(/\s+/g, " ").trim()
}

export function derivePaperTitleFromFilename(filename) {
  const base = stripExtension(filename)
  return normalizeWhitespace(base)
}

export function shouldAutoFillPaperTitle(currentTitle, previousAutoFilledTitle) {
  const current = String(currentTitle || "").trim()
  const previous = String(previousAutoFilledTitle || "").trim()
  return !current || (previous && current === previous)
}

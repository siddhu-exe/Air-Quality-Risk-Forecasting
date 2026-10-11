/** First tab stop: lets keyboard users jump past the header to the page content. */
export function SkipLink() {
  return (
    <a
      href="#main"
      className="sr-only rounded-full no-underline bg-ink px-4 py-2 text-white focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 hover:text-white"
    >
      Skip to content
    </a>
  )
}

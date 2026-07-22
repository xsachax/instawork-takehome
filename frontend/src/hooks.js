import { useEffect } from 'react'

// Sets the document title for a page (helps screen-reader users know where they
// are after a client-side navigation).
export function useDocumentTitle(title) {
  useEffect(() => {
    document.title = title ? `${title} · Quiz Platform` : 'Quiz Platform'
  }, [title])
}

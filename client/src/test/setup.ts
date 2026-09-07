// Vitest global setup.
import '@testing-library/jest-dom/vitest'

import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

// Testing Library only registers its automatic afterEach cleanup when Vitest
// `globals` are enabled. This project uses explicit imports instead, so the
// cleanup is registered here — without it, renders leak between tests.
afterEach(() => {
  cleanup()
})

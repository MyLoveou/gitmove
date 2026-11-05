import type { GitmoveApi } from '../../preload/index'

declare global {
  interface Window {
    gitmove: GitmoveApi
  }
}

export {}

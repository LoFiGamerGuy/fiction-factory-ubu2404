/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
  readonly VITE_DEFAULT_RUN_ID?: string;
  readonly VITE_DEFAULT_BOOK_ID?: string;
  readonly VITE_DEFAULT_SERIES_ID?: string;
  readonly VITE_DEFAULT_CHARACTER_IDS?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE?: string;
  readonly VITE_USE_MOCK?: string;
  readonly VITE_MOCK_SPEED?: string;
  readonly VITE_ENV_LABEL?: string;
  readonly VITE_EXPLORER_BASE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

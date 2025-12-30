interface ImportMeta {
  readonly env: ImportMetaEnv
}

interface ImportMetaEnv {
  /**
   * Built-in environment variable.
   * @example
   * 'production'
   */
  readonly MODE: string

  /**
   * Built-in environment variable.
   * @example
   * 'https://serene-rain-forest-8848.fly.dev'
   */
  readonly VITE_API_URL: string

  // Add other environment variables as needed
  readonly [key: string]: any
}
// CSS Modules
declare module "*.module.css" {
  const classes: { [key: string]: string };
  export default classes;
}
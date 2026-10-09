export type Settings = {
  provider: string; cloud_ai_allowed: boolean; gemini_free_tier_confirmed: boolean; gemini_model: string; ollama_model: string;
  approved_roots: string[]; microphone: boolean; screen: boolean; camera: boolean; automation: boolean;
  tool_execution: boolean; learning: boolean; language: string; voice_enabled: boolean; voice_model: string;
  whisper_model: string; wake_model: string; speech_rate: number; volume: number; retention_days: number;
  sync_enabled: boolean; supabase_url: string; supabase_anon_key: string; cloud_url: string;
  google_client_file: string; google_scopes: string[]; custom_endpoint: string; custom_model: string; custom_free_confirmed: boolean;
};
export type Task = {id: string; action: string; args: Record<string, unknown>; status: string; risk: string; result?: unknown; error?: string; expires?: number; created: number};
export type Action = {name: string; description: string; schema: {properties: Record<string, {type: string; enum?: string[]; description?: string}>; required: string[]}; risk: string; scheduled: boolean};
export type Message = {role: string; content: string};
export type Status = {
  busy: boolean; budget: string; permissions: Record<string, boolean>;
  voice: {state: string; running: boolean; transcript: string; conversation_id?: string; error?: string; echo_mode: string};
  ai: {ollama: {models: string[]; error?: string; configured_model: string}; gemini: {key_present: boolean; free_confirmed: boolean; model: string}};
  google: {connected: boolean}; cloud: {configured: boolean; signed_in: boolean};
};
export type Connection = {base: string; token: string; mode: 'local' | 'cloud'; deviceToken?: string; supabaseUrl?: string; supabaseKey?: string};
declare global {interface Window {ultron?: {session(): Promise<Connection>; openExternal(url: string): Promise<void>; notify(title: string, body: string): Promise<void>}}}

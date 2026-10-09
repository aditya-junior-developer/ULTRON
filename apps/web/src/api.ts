import type { Connection } from './types';
export class API {
  constructor(public connection: Connection) {}
  async request<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
    const response = await fetch(this.connection.base.replace(/\/$/, '') + path, {
      method, headers: {'Authorization': `Bearer ${this.connection.token}`, ...(this.connection.deviceToken?{'X-ULTRON-Device-Token':this.connection.deviceToken}:{}), ...(body !== undefined ? {'Content-Type': 'application/json'} : {})},
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
    const data = await response.json().catch(() => ({detail: 'Invalid server response'}));
    if (!response.ok) throw new Error(data.detail || data.error || `Request failed (${response.status})`);
    return data as T;
  }
}

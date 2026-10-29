/**
 * 接口基地址：本地开发 `'/api'`（vite 代理到 8000），
 * 生产构建由 `.env.production` 的 `VITE_API_BASE=/majiangapi` 覆盖（06 §8.2）。
 * 协议形状不变——只是前缀，所有路径仍按 04 的 `/api/...` 相对书写。
 */
const BASE = (import.meta.env.VITE_API_BASE as string) || '/api'
const TOKEN_KEY = 'mj_token'
const USER_KEY = 'mj_user'

export function getToken(): string {
  return localStorage.getItem(TOKEN_KEY) || ''
}

export function setToken(token: string): void {
  if (token) localStorage.setItem(TOKEN_KEY, token)
  else localStorage.removeItem(TOKEN_KEY)
}

export function getStoredUser(): unknown {
  const raw = localStorage.getItem(USER_KEY)
  if (!raw) return null
  try {
    return JSON.parse(raw)
  } catch {
    return null
  }
}

export function setStoredUser(user: unknown): void {
  if (user) localStorage.setItem(USER_KEY, JSON.stringify(user))
  else localStorage.removeItem(USER_KEY)
}

export class ApiError extends Error {
  status: number
  /** 04 §1 的错误码（如 ACCOUNT_AUTH_FAILED / VERIFY_CODE_INVALID），无则空串 */
  code: string
  constructor(status: number, message: string, code = '') {
    super(message)
    this.status = status
    this.code = code
  }
}

let unauthorizedHandler: () => void = () => {}

export function onUnauthorized(handler: () => void): void {
  unauthorizedHandler = handler
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`

  const response = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body)
  })

  if (response.status === 401) {
    unauthorizedHandler()
    throw new ApiError(401, '登录已失效，请重新登录')
  }

  const text = await response.text()
  const payload = text ? safeParse(text) : null

  if (!response.ok) {
    const detail = (payload && (payload.detail || payload.message)) || '请求失败，请稍后再试'
    const code = (payload && typeof payload.code === 'string' && payload.code) || ''
    throw new ApiError(
      response.status,
      typeof detail === 'string' ? detail : '请求失败',
      code
    )
  }
  return payload as T
}

export interface MetaResponse<T> {
  /** 304 或响应体为空时为 null */
  data: T | null
  status: number
  /** `GET /api/skins` 的清单指纹（04 §8） */
  etag: string
  /** 304 命中本地缓存 */
  notModified: boolean
}

/**
 * 带响应头的 GET：皮肤清单需要 `If-None-Match` → 304 协商（04 §8、05 §6.4）。
 * 其余接口用 `api.get` 即可。
 */
async function getWithMeta<T>(path: string, etag = ''): Promise<MetaResponse<T>> {
  const headers: Record<string, string> = {}
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`
  if (etag) headers['If-None-Match'] = etag

  const response = await fetch(`${BASE}${path}`, { method: 'GET', headers })

  if (response.status === 401) {
    unauthorizedHandler()
    throw new ApiError(401, '登录已失效，请重新登录')
  }

  const responseEtag = response.headers.get('ETag') || etag

  if (response.status === 304) {
    return { data: null, status: 304, etag: responseEtag, notModified: true }
  }

  const text = await response.text()
  const payload = text ? safeParse(text) : null

  if (!response.ok) {
    const detail = (payload && (payload.detail || payload.message)) || '请求失败，请稍后再试'
    const code = (payload && typeof payload.code === 'string' && payload.code) || ''
    throw new ApiError(response.status, typeof detail === 'string' ? detail : '请求失败', code)
  }
  return { data: payload as T, status: response.status, etag: responseEtag, notModified: false }
}

/**
 * 上传单个文件（04 §8 #38 的 `multipart/form-data: file`）。
 * 不能手动设 `Content-Type`，否则浏览器不会带上 boundary。
 */
async function upload<T>(path: string, file: File, fieldName = 'file'): Promise<T> {
  const headers: Record<string, string> = {}
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`

  const form = new FormData()
  form.append(fieldName, file, file.name)

  const response = await fetch(`${BASE}${path}`, { method: 'PUT', headers, body: form })

  if (response.status === 401) {
    unauthorizedHandler()
    throw new ApiError(401, '登录已失效，请重新登录')
  }

  const text = await response.text()
  const payload = text ? safeParse(text) : null

  if (!response.ok) {
    const detail = (payload && (payload.detail || payload.message)) || '上传失败，请稍后再试'
    const code = (payload && typeof payload.code === 'string' && payload.code) || ''
    throw new ApiError(response.status, typeof detail === 'string' ? detail : '上传失败', code)
  }
  return payload as T
}

function safeParse(text: string): any {
  try {
    return JSON.parse(text)
  } catch {
    return null
  }
}

export const api = {
  get: <T>(path: string) => request<T>('GET', path),
  post: <T>(path: string, body?: unknown) => request<T>('POST', path, body),
  put: <T>(path: string, body?: unknown) => request<T>('PUT', path, body),
  patch: <T>(path: string, body?: unknown) => request<T>('PATCH', path, body),
  del: <T>(path: string) => request<T>('DELETE', path),
  getWithMeta,
  upload
}

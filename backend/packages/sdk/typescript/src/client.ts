/**
 * Astloom TypeScript HTTP client.
 * Parity with Python astloom_sdk: GET/POST, X-Correlation-Id, Idempotency-Key.
 */

export class SdkError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "SdkError";
  }
}

export type AstloomClientOptions = {
  baseUrl: string;
  defaultHeaders?: Record<string, string>;
  apiPrefix?: string;
  fetchImpl?: typeof fetch;
};

export type RequestBuild = {
  method: string;
  url: string;
  headers: Record<string, string>;
};

export class AstloomClient {
  readonly baseUrl: string;
  readonly apiPrefix: string;
  readonly defaultHeaders: Record<string, string>;
  private readonly fetchImpl: typeof fetch;

  constructor(options: AstloomClientOptions) {
    const base = (options.baseUrl || "").trim();
    if (!base) {
      throw new SdkError("base_url is required");
    }
    this.baseUrl = base.replace(/\/+$/, "") + "/";
    this.apiPrefix = (options.apiPrefix ?? "/api/v1").replace(/\/+$/, "");
    this.defaultHeaders = { ...(options.defaultHeaders ?? {}) };
    this.fetchImpl = options.fetchImpl ?? fetch;
  }

  url(path: string): string {
    let relative = path.startsWith("/") ? path : `/${path}`;
    if (!relative.startsWith(this.apiPrefix)) {
      relative = `${this.apiPrefix}${relative}`;
    }
    return new URL(relative.replace(/^\//, ""), this.baseUrl).toString();
  }

  headers(opts?: {
    correlationId?: string;
    idempotencyKey?: string;
    extra?: Record<string, string>;
  }): Record<string, string> {
    const headers = { ...this.defaultHeaders };
    if (opts?.correlationId) {
      headers["X-Correlation-Id"] = opts.correlationId;
    }
    if (opts?.idempotencyKey) {
      headers["Idempotency-Key"] = opts.idempotencyKey;
    }
    if (opts?.extra) {
      Object.assign(headers, opts.extra);
    }
    return headers;
  }

  buildRequest(
    method: string,
    path: string,
    opts?: {
      correlationId?: string;
      idempotencyKey?: string;
      headers?: Record<string, string>;
    },
  ): RequestBuild {
    const verb = (method || "").trim().toUpperCase();
    if (!verb) {
      throw new SdkError("method is required");
    }
    return {
      method: verb,
      url: this.url(path),
      headers: this.headers({
        correlationId: opts?.correlationId,
        idempotencyKey: opts?.idempotencyKey,
        extra: opts?.headers,
      }),
    };
  }

  async request(
    method: string,
    path: string,
    opts?: {
      json?: unknown;
      correlationId?: string;
      idempotencyKey?: string;
      headers?: Record<string, string>;
    },
  ): Promise<Response> {
    const built = this.buildRequest(method, path, opts);
    const init: RequestInit = {
      method: built.method,
      headers: { ...built.headers },
    };
    if (opts?.json !== undefined) {
      (init.headers as Record<string, string>)["Content-Type"] =
        "application/json";
      init.body = JSON.stringify(opts.json);
    }
    return this.fetchImpl(built.url, init);
  }

  get(
    path: string,
    opts?: {
      correlationId?: string;
      idempotencyKey?: string;
      headers?: Record<string, string>;
    },
  ): Promise<Response> {
    return this.request("GET", path, opts);
  }

  post(
    path: string,
    opts?: {
      json?: unknown;
      correlationId?: string;
      idempotencyKey?: string;
      headers?: Record<string, string>;
    },
  ): Promise<Response> {
    return this.request("POST", path, opts);
  }
}

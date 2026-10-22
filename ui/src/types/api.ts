// Error body returned by the blog-agent API (src/libs/exceptions/handlers.py) and the UI proxy.
export type TApiErrorBody = {
  code: string;
  message: string;
  request_id?: string | null;
  details?: unknown;
};

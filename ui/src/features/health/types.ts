// Mirrors HealthCheckResponseDto in api/src/modules/health/presenter/dtos/health_dto.py
export type THealthStatus = "healthy" | "degraded";

export type THealth = {
  status: THealthStatus;
  app: string;
  env: string;
  database: { ok: boolean };
  checkpointer: { ok: boolean };
  llm: {
    configured: boolean;
    default_provider: string | null;
    roles: Record<string, string | null>;
  };
  tracing: {
    enabled: boolean;
    project: string | null;
  };
};

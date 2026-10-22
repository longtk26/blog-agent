import { proxyToAgent } from "@/lib/server/agent-proxy";

type AgentRouteContext = RouteContext<"/api/agent/[...path]">;

async function handle(request: Request, ctx: AgentRouteContext) {
  const { path } = await ctx.params;
  return proxyToAgent(request, path);
}

export const GET = handle;
export const POST = handle;
export const PUT = handle;
export const PATCH = handle;
export const DELETE = handle;

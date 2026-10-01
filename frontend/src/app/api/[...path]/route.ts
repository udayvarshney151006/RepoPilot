import type { NextRequest } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
const maximumUploadBytes = 25 * 1024 * 1024 + 64 * 1024;
const requestIdPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

async function proxy(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
) {
  const { path } = await context.params;
  if (
    path.some(
      (segment) =>
        segment === ".." || segment === "." || segment.includes("\\"),
    )
  ) {
    return Response.json({ detail: "Invalid API path." }, { status: 400 });
  }
  const origin = (
    process.env.SERVER_API_URL || "http://127.0.0.1:8000"
  ).replace(/\/$/, "");
  const url = `${origin}/api/${path.map(encodeURIComponent).join("/")}${request.nextUrl.search}`;
  const headers = new Headers();
  const clientRequestId = request.headers.get("x-request-id");
  if (clientRequestId?.length === 36 && requestIdPattern.test(clientRequestId))
    headers.set("x-request-id", clientRequestId.toLowerCase());
  const contentType = request.headers.get("content-type");
  if (contentType) headers.set("content-type", contentType);
  const isUpload = path.join("/") === "repositories/upload";
  const contentLength = request.headers.get("content-length");
  if (contentLength !== null) {
    if (
      !/^\d+$/.test(contentLength) ||
      !Number.isSafeInteger(Number(contentLength))
    ) {
      return Response.json(
        { detail: "Invalid request content length." },
        { status: 400 },
      );
    }
    if (isUpload && Number(contentLength) > maximumUploadBytes) {
      return Response.json(
        { detail: "Repository upload exceeds the 25 MB limit." },
        { status: 413 },
      );
    }
    headers.set("content-length", contentLength);
  }
  if (process.env.SERVER_API_AUTH_TOKEN)
    headers.set("authorization", `Bearer ${process.env.SERVER_API_AUTH_TOKEN}`);
  try {
    const options: RequestInit & { duplex?: string } = {
      method: request.method,
      headers,
      cache: "no-store",
      redirect: "error",
      signal: AbortSignal.timeout(120000),
    };
    if (!["GET", "HEAD"].includes(request.method)) {
      if (isUpload && contentLength === null) {
        // Multipart parsers need a bounded length before spooling an upload.
        // When a client omits it, buffer only up to the explicit transport limit.
        const chunks: Uint8Array[] = [];
        let bytes = 0;
        const reader = request.body?.getReader();
        if (reader) {
          while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            bytes += value.byteLength;
            if (bytes > maximumUploadBytes) {
              await reader.cancel();
              return Response.json(
                { detail: "Repository upload exceeds the 25 MB limit." },
                { status: 413 },
              );
            }
            chunks.push(value);
          }
        }
        const body = new Uint8Array(bytes);
        let offset = 0;
        for (const chunk of chunks) {
          body.set(chunk, offset);
          offset += chunk.byteLength;
        }
        options.body = body;
        headers.set("content-length", String(bytes));
      } else {
        options.body = request.body;
        options.duplex = "half";
      }
    }
    const upstream = await fetch(url, options);
    const responseHeaders = new Headers({
      "content-type":
        upstream.headers.get("content-type") || "application/json",
      "cache-control": "no-store",
    });
    const requestId = upstream.headers.get("x-request-id");
    if (requestId?.length === 36 && requestIdPattern.test(requestId))
      responseHeaders.set("x-request-id", requestId.toLowerCase());
    return new Response(upstream.body, {
      status: upstream.status,
      headers: responseHeaders,
    });
  } catch {
    return Response.json(
      {
        detail:
          "Cannot reach the RepoPilot backend. Start the API service and check SERVER_API_URL.",
      },
      { status: 502 },
    );
  }
}
export const GET = proxy;
export const POST = proxy;

import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL =
  process.env.BACKEND_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://localhost:8000";

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  return proxy(request, await params);
}

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  return proxy(request, await params);
}

export async function PUT(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  return proxy(request, await params);
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  return proxy(request, await params);
}

async function proxy(request: NextRequest, params: { path: string[] }) {
  const path = params.path.join("/");
  const search = request.nextUrl.search;
  const url = `${BACKEND_URL}/${path}${search}`;
  const headers = new Headers(request.headers);
  // Remove headers hop-by-hop / de conexão que quebram o fetch do Node (undici)
  // ao repassar a requisição. Manter content-length/transfer-encoding causa
  // "TypeError: fetch failed" em métodos POST/PATCH.
  headers.delete("host");
  headers.delete("connection");
  headers.delete("content-length");
  headers.delete("transfer-encoding");
  headers.delete("accept-encoding");

  const init: RequestInit = {
    method: request.method,
    headers,
  };

  if (request.method !== "GET" && request.method !== "HEAD") {
    const buf = await request.arrayBuffer();
    // Só envia body se houver conteúdo (ex: login é POST sem body)
    if (buf.byteLength > 0) {
      init.body = buf;
    }
  }

  try {
    const res = await fetch(url, init);
    const body = await res.arrayBuffer();

    return new NextResponse(body, {
      status: res.status,
      headers: {
        "content-type": res.headers.get("content-type") || "application/json",
      },
    });
  } catch (err) {
    return NextResponse.json(
      { error: "Backend unavailable", detail: String(err) },
      { status: 502 }
    );
  }
}

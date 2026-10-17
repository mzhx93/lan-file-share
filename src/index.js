import { DurableObject } from "cloudflare:workers";

// Durable Object：每个房间一个实例，负责在两端之间转发 WebRTC 信令（offer/answer/ICE）。
export class Room extends DurableObject {
  constructor(ctx, env) {
    super(ctx, env);
    this.sessions = new Map();
    this.ctx.getWebSockets().forEach((ws) => {
      const att = ws.deserializeAttachment();
      if (att) this.sessions.set(ws, att);
    });
  }

  async fetch(request) {
    if (this.sessions.size >= 2) {
      return new Response("Room is full", { status: 409 });
    }
    const pair = new WebSocketPair();
    const [client, server] = Object.values(pair);
    this.ctx.acceptWebSocket(server);
    const id = crypto.randomUUID();
    server.serializeAttachment({ id });
    this.sessions.set(server, { id });
    return new Response(null, { status: 101, webSocket: client });
  }

  async webSocketMessage(ws, message) {
    const data = typeof message === "string" ? message : new TextDecoder().decode(message);
    for (const [other] of this.sessions) {
      if (other !== ws) {
        try { other.send(data); } catch (e) {}
      }
    }
  }

  async webSocketClose(ws, code, reason, wasClean) {
    this.sessions.delete(ws);
    for (const [other] of this.sessions) {
      try { other.send(JSON.stringify({ type: "peer-left" })); } catch (e) {}
    }
    try { ws.close(code, reason); } catch (e) {}
  }

  async webSocketError(ws, error) {
    this.sessions.delete(ws);
  }
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    if (url.pathname.startsWith("/room/")) {
      const roomId = url.pathname.slice("/room/".length);
      if (!roomId) return new Response("Bad request", { status: 400 });
      const upgradeHeader = request.headers.get("Upgrade");
      if (!upgradeHeader || upgradeHeader.toLowerCase() !== "websocket") {
        return new Response("Expected WebSocket upgrade", { status: 426 });
      }
      const stub = env.ROOM.getByName(roomId);
      return stub.fetch(request);
    }
    return env.ASSETS.fetch(request);
  },
};

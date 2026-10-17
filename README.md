# lan-file-share · Chrome 浏览器版（纯局域网 · Cloudflare 部署）

基于 **WebRTC 点对点** 的局域网文件共享，一键部署到 **Cloudflare Workers**。

## 原理
- 文件通过 WebRTC DataChannel **点对点直传**，数据不出局域网、不经过任何服务器。
- Cloudflare 仅承载网页与 WebRTC 信令（交换 offer/answer/ICE 的小段 JSON）。
- 关闭网页即结束共享：文件只存在于发送端浏览器内存，关掉页面就没有任何人能再下载。

## 使用体验
1. 打开网页，只有“开启局域网共享服务”一个按钮。
2. 点击后选择文件夹/文件，生成二维码。
3. 手机（同一局域网）扫码，等待点对点连接，逐个保存文件。
4. 关闭电脑端网页 = 退出共享。

## 部署到 Cloudflare
1. 安装依赖并登录：
   ```
   npm install
   npx wrangler login
   ```
2. 部署：
   ```
   npm run deploy
   ```
3. 用返回的 https 地址访问（Cloudflare 默认提供 HTTPS）。本地调试：`npm run dev`（http://localhost:8787）。

## 结构
- src/index.js — Worker（/room/* 路由到 Durable Object，其余走静态资源）
- public/index.html — 前端（发送/接收一体）
- wrangler.jsonc — 配置（Durable Object 绑定 + 静态资源 + 迁移）

## 说明
- 信令依赖 Cloudflare（需能访问到 worker），文件传输本身走局域网 P2P。
- 同一子网（常见同一 Wi-Fi）下无需任何 STUN/TURN；跨网段需自行在 index.html 中给 RTCPeerConnection 加 STUN 服务器。

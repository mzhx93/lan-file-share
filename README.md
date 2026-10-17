# lan-file-share · Chrome 浏览器版

基于 **WebRTC（WebTorrent）** 的局域网文件/目录共享工具，无需安装 Python，直接在 Chrome 浏览器里运行。

## 特性
- 点对点(P2P)直传，文件不经过服务器。
- 手机扫二维码即可预览/下载。
- 支持文件夹（File System Access API）与多文件。

## 使用前提
- 两端设备需能访问互联网（用于 WebRTC 信令/STUN 与 WebTorrent tracker），实际文件走 P2P。
- 页面需通过 HTTPS 访问（例如 GitHub Pages），否则 WebRTC 不可用。

## 快速开始
1. 在本仓库开启 GitHub Pages（Settings → Pages → 部署 chrome 分支根目录）。
2. 电脑 Chrome 打开页面，点击“选择文件夹/文件”。
3. 生成二维码后，手机（同一局域网即可）扫码，等待连接并下载。

> 若手机与电脑不在同一局域网，也可通过公网 P2P 传输（取决于网络可达性）。

## 文件
- index.html — 单文件应用（发送端 + 接收端一体）。
- 依赖：WebTorrent、qrcode-generator（通过 CDN 加载）。

## 说明
- 与 windows 分支的 Python 版相比，本版无需运行服务端，但依赖公网 WebRTC 基础设施做信令。
- iOS Safari 下载时可能以“分享/另存”方式呈现，长按保存即可。

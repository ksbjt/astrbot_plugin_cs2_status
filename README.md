# astrbot_plugin_cs2_status

### 介绍

- 查询 CS2 服务器信息

---

### 数据来源

- 插件通过 HTTP API 获取服务器状态，不再依赖 MySQL。
- 可通过配置项 `serverlist_url` 覆盖默认地址。

### API 返回示例

```json
{
  "updated_at": "2026-02-27 08:43:13",
  "last_error": null,
  "servers": []
}
```

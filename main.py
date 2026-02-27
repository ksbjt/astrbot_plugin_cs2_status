import asyncio
import json
from urllib import error, request
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger


@register(
    "astrbot_plugin_cs2_status",
    "ksbjt",
    "查询 CS2 服务器信息",
    "1.2.6",
)
class CS2StatusPlugin(Star):
    SERVERLIST_URL = "https://kep.kaish.cn/api/serverlist?key=kaish"

    def __init__(self, context: Context, config: dict):
        super().__init__(context)
        self.config = config if config else context.config

    @filter.command("status")
    async def server_status(self, event: AstrMessageEvent):
        """Query kep server list"""

        loading_msg = await event.send(
            event.plain_result("Querying server information...")
        )

        GROUP_MAP = {
            "ze_practice": "Practice map",
            "ze": "Play map (no practice stp)",
        }

        try:
            # 1. 异步拉取 API 服务器列表
            payload = await asyncio.to_thread(self._fetch_server_list)
            rows = payload.get("servers", [])
            updated_at = payload.get("updated_at")

            if not rows:
                if loading_msg:
                    await loading_msg.edit(
                        event.plain_result("No server data from API")
                    )
                return

            # 2. 直接使用 API 返回状态
            results = [self._build_result(s) for s in rows]

            # 全部超时时，输出统一英文提示
            all_failed = len(results) > 0 and all(
                res.get("timed_out", False) for res in results
            )
            if all_failed and len(rows) > 0:
                if loading_msg:
                    await loading_msg.edit(
                        event.plain_result(
                            "All servers timed out.\nPossible network instability or the game is being updated/under maintenance."
                        )
                    )
                else:
                    yield event.plain_result(
                        "All servers timed out.\nPossible network instability or the game is being updated/under maintenance."
                    )
                return

            # 3. 按组组织数据（隐藏非空闲服务器）
            grouped_data = {}
            total_players = 0
            hidden_non_idle_count = 0

            for res in results:
                total_players += res["player_count"]
                if (not res.get("timed_out", False)) and res["player_count"] > 0:
                    hidden_non_idle_count += 1
                    continue
                group = res["group"]
                if group not in grouped_data:
                    grouped_data[group] = []
                grouped_data[group].append(res)

            # 4. 构建输出消息
            output = []
            output.append("Kep Server List")
            if updated_at:
                output.append(f"Updated at: `{updated_at}`")

            for group_key in sorted(grouped_data.keys(), reverse=True):
                display_name = GROUP_MAP.get(group_key, group_key)
                output.append(f"📡 **{display_name}** 📡")
                for res in grouped_data[group_key]:
                    output.append(res["line"])
                output.append("")

            output.append(f"Total player: **{total_players}**")
            if hidden_non_idle_count > 0:
                output.append("Non-idle servers are hidden")
            final_text = "\n".join(output)

            # 5. 【核心修改】使用返回对象的 edit 方法进行原地覆盖
            if loading_msg:
                await loading_msg.edit(event.plain_result(final_text))
            else:
                # 如果因为某种原因没拿到 loading_msg，则保底发送一条新消息
                yield event.plain_result(final_text)

        except Exception as e:
            logger.error(f"Runtime error: {e}")
            if loading_msg:
                await loading_msg.edit(event.plain_result(f"Query error: {str(e)}"))
            else:
                yield event.plain_result(f"Query error: {str(e)}")

    def _fetch_server_list(self):
        url = self.config.get("serverlist_url", self.SERVERLIST_URL)
        req = request.Request(url=url, headers={"User-Agent": "astrbot-cs2-status/1.2.5"})
        try:
            with request.urlopen(req, timeout=5) as resp:
                data = resp.read().decode("utf-8")
        except error.URLError as e:
            raise RuntimeError(f"Failed to fetch API: {e}") from e

        try:
            payload = json.loads(data)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Invalid API JSON: {e}") from e

        if not isinstance(payload, dict):
            raise RuntimeError("Invalid API response: root should be an object")
        if "servers" not in payload or not isinstance(payload["servers"], list):
            raise RuntimeError("Invalid API response: missing servers array")

        return payload

    def _build_result(self, server):
        name = server.get("name", "Unknown")
        host = server.get("host", "0.0.0.0")
        port = server.get("port", 0)
        group = server.get("mode", "other")
        status = str(server.get("status", "")).lower()
        api_error = server.get("error")

        current_players = server.get("current_players")
        max_players = server.get("max_players")
        map_name = server.get("map") or "Unknown"

        player_count = current_players if isinstance(current_players, int) else 0
        is_ok = status == "ok"

        if is_ok:
            line = (
                f"· {name} ( {player_count} / {max_players if max_players is not None else '?'} )\n"
                f"Map: **{map_name}**\n"
                f"__Connect {host}:{port}__"
            )
        else:
            detail = api_error or status or "UnknownError"
            line = f"· {name} TimeoutError ({detail})\n__Connect {host}:{port}__"

        return {
            "group": group,
            "line": line,
            "player_count": player_count if is_ok else 0,
            "timed_out": not is_ok,
        }

    async def terminate(self):
        logger.info("uninstalled: astrbot_plugin_cs2_status")

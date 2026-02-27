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
    "1.3.7",
)
class CS2StatusPlugin(Star):
    SERVERLIST_URL = "https://kep.kaish.cn/api/serverlist?key=kaish"

    def __init__(self, context: Context):
        super().__init__(context)

    @filter.command("status")
    async def server_status(self, event: AstrMessageEvent):
        """Query Kep ServerList"""

        GROUP_MAP = {
            "ze": "Play map",
            "ze_practice": "Practice map",
        }
        GROUP_ORDER = {
            "ze_practice": 0,
            "ze": 1,
        }

        try:
            payload = await asyncio.to_thread(self._fetch_server_list)
            rows = payload.get("servers", [])

            if not rows:
                yield event.plain_result("No server data from API")
                return

            results = [self._build_result(s) for s in rows]

            all_unavailable = results and all(
                res.get("is_unavailable", False) for res in results
            )
            if all_unavailable:
                yield event.plain_result(
                    "All servers unavailable\nOr being updated/maintained"
                )
                return

            grouped_data = {}
            total_players = 0
            hidden_non_idle_count = 0

            for res in results:
                total_players += res["player_count"]
                if (not res.get("is_unavailable", False)) and res["player_count"] > 0:
                    hidden_non_idle_count += 1
                    continue
                group = res["group"]
                if group not in grouped_data:
                    grouped_data[group] = []
                grouped_data[group].append(res)

            output = []
            output.append("Kep ServerList")

            for group_key in sorted(
                grouped_data.keys(),
                key=lambda k: (GROUP_ORDER.get(k, 99), k),
            ):
                display_name = GROUP_MAP.get(group_key, group_key)
                output.append(f"**--- {display_name} ---**")
                for res in grouped_data[group_key]:
                    output.append(res["line"])
                output.append("")

            output.append(f"Total player: **{total_players}**")
            if hidden_non_idle_count > 0:
                output.append("__Non idle server hidden__")
            final_text = "\n".join(output)
            yield event.plain_result(final_text)

        except Exception as e:
            logger.exception(f"Runtime error: {e}")
            yield event.plain_result(f"Query error: {str(e)}")

    def _fetch_server_list(self):
        req = request.Request(
            url=self.SERVERLIST_URL,
            headers={"User-Agent": "astrbot_plugin_cs2_status"},
        )
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
        status = str(server.get("status", "")).strip().lower()
        api_error = server.get("error")

        current_players = server.get("current_players")
        max_players = server.get("max_players")
        map_name = server.get("map") or "Unknown"

        player_count = (
            current_players
            if type(current_players) is int and current_players >= 0
            else 0
        )
        max_count = (
            max_players if type(max_players) is int and max_players >= 0 else "?"
        )
        is_ok = status == "ok"

        if is_ok:
            line = (
                f"· {name} ( {player_count} / {max_count} )\n"
                f"Map: **{map_name}**\n"
                f"Join: [{host}:{port}](https://vauff.com/connect.php?ip={host}:{port})"
            )
        else:
            status_text = status or "unknown"
            if api_error:
                line = (
                    f"· {name} ( {status_text} ) ({api_error})\n"
                    f"Join: [{host}:{port}](https://vauff.com/connect.php?ip={host}:{port})"
                )
            else:
                line = (
                    f"· {name} ( {status_text} )\n"
                    f"Join: [{host}:{port}](https://vauff.com/connect.php?ip={host}:{port})"
                )

        return {
            "group": group,
            "line": line,
            "player_count": player_count if is_ok else 0,
            "is_unavailable": not is_ok,
        }

    async def terminate(self):
        logger.info("卸载插件: astrbot_plugin_cs2_status")

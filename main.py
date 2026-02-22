import asyncio
import socket
import mysql.connector
import a2s
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger


@register(
    "astrbot_plugin_cs2_status",
    "ksbjt",
    "查询 CS2 服务器信息",
    "1.2.5",
)
class CS2StatusPlugin(Star):
    def __init__(self, context: Context, config: dict):
        super().__init__(context)
        self.config = config if config else context.config

    def _get_db_conn(self):
        return mysql.connector.connect(
            host=self.config.get("db_host", "127.0.0.1"),
            port=int(self.config.get("db_port", 3306)),
            user=self.config.get("db_user", "root"),
            password=self.config.get("db_pass", ""),
            database=self.config.get("db_name", "cs2_serverlist"),
            connect_timeout=5,
        )

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
            # 1. 异步获取数据库服务器列表
            rows = await asyncio.to_thread(self._fetch_server_list)

            if not rows:
                if loading_msg:
                    await loading_msg.edit(
                        event.plain_result("No enabled configuration in the database")
                    )
                return

            # 2. 并行查询 A2S 接口
            tasks = [self._query_a2s(s) for s in rows]
            results = await asyncio.gather(*tasks)

            # 全部查询超时时，输出统一英文提示
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
        conn = None
        try:
            conn = self._get_db_conn()
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                "SELECT name, host, port, mode FROM servers WHERE is_active = 1 ORDER BY mode DESC"
            )
            rows = cursor.fetchall()
            cursor.close()
            return rows
        finally:
            if conn and conn.is_connected():
                conn.close()

    async def _query_a2s(self, s):
        host, port = s["host"], s["port"]
        name, group = s["name"], s["mode"]
        timeout_errors = (TimeoutError, asyncio.TimeoutError, socket.timeout)
        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                # 增加超时控制：超时后最多重试两次，减少网络抖动影响
                info = await asyncio.to_thread(a2s.info, (host, port), timeout=2.0)
                line = f"· {name} ( {info.player_count} / {info.max_players} )\nMap: **{info.map_name}**\n__Connect {host}:{port}__"
                return {
                    "group": group,
                    "line": line,
                    "player_count": info.player_count,
                    "timed_out": False,
                }
            except timeout_errors as e:
                if attempt < max_retries:
                    logger.warning(
                        f"A2S query timeout, retry {attempt + 1}/{max_retries}: {host}:{port}, error={e}"
                    )
                    continue
                line = f"· {name} TimeoutError\n__Connect {host}:{port}__"
                return {
                    "group": group,
                    "line": line,
                    "player_count": 0,
                    "timed_out": True,
                }
            except Exception:
                line = f"· {name} TimeoutError\n__Connect {host}:{port}__"
                return {
                    "group": group,
                    "line": line,
                    "player_count": 0,
                    "timed_out": True,
                }

    async def terminate(self):
        logger.info("uninstalled: astrbot_plugin_cs2_status")

import asyncio
import mysql.connector
import a2s
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger


@register(
    "astrbot_plugin_cs2_status",
    "ksbjt",
    "查询 CS2 服务器信息",
    "1.1.2",
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
        """Query Kep server information"""

        # 1. 发送初始消息，并获取返回的消息对象
        # 注意：这里需要 await，且 loading_msg 将是 AstrBot 封装的消息引用
        loading_msg = await event.send(event.plain_result("Querying server information..."))

        GROUP_MAP = {
            "ze_practice": "**__Single player practice map__**",
            "ze": "**__Play the map (No practice stripper)__**"
        }

        try:
            # 1. 异步获取数据库服务器列表
            rows = await asyncio.to_thread(self._fetch_server_list)

            if not rows:
                if loading_msg:
                    await loading_msg.edit(event.plain_result("No enabled configuration in the database"))
                return

            # 2. 并行查询 A2S 接口
            tasks = [self._query_a2s(s) for s in rows]
            results = await asyncio.gather(*tasks)

            # 3. 按组组织数据
            grouped_data = {}
            total_players = 0

            for res in results:
                group = res["group"]
                total_players += res["player_count"]
                if group not in grouped_data:
                    grouped_data[group] = []
                grouped_data[group].append(res)

            # 4. 构建输出消息
            output = []
            for group_key in sorted(grouped_data.keys(), reverse=True):
                display_name = GROUP_MAP.get(group_key, group_key)
                output.append(f"↓ {display_name} ↓")
                for res in grouped_data[group_key]:
                    output.append(res["line"])
                output.append("")

            output.append(f"Total player: `{total_players}`")
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
                "SELECT name, host, port, group_name FROM servers WHERE is_active = 1 ORDER BY group_name DESC"
            )
            rows = cursor.fetchall()
            cursor.close()
            return rows
        finally:
            if conn and conn.is_connected():
                conn.close()

    async def _query_a2s(self, s):
        host, port = s["host"], s["port"]
        name, group = s["name"], s["group_name"]
        try:
            # 增加超时控制
            info = await asyncio.to_thread(a2s.info, (host, port), timeout=2.0)
            # 简洁格式：名称 |=> 地图 (人数/上限) IP:端口
            line = f"{name} `{info.map_name}`\n└`({info.player_count}/{info.max_players})` `{host}:{port}`"
            return {"group": group, "line": line, "player_count": info.player_count}
        except Exception:
            line = f"{name} Query timeout\n└`(0/0)` `{host}:{port}`"
            return {"group": group, "line": line, "player_count": 0}

    async def terminate(self):
        logger.info("uninstalled: astrbot_plugin_cs2_status")
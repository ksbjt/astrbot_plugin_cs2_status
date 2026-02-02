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
    "1.0.1",
)
class CS2StatusPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.config = context.config

    def get_db_conn(self):
        return mysql.connector.connect(
            host=self.config.get("db_host", "127.0.0.1"),
            port=self.config.get("db_port", 3306),
            user=self.config.get("db_user", "root"),
            password=self.config.get("db_pass", ""),
            database=self.config.get("db_name", "cs2_serverlist"),
            connect_timeout=5
        )

    @filter.command("status")
    async def server_status(self, event: AstrMessageEvent):
        '''获取并显示 CS2 服务器实时状态和在线人数'''
        # ↑ 上面这一行 Docstring 会被 Discord 识别为指令描述 (类似你图片中的效果)

        yield event.plain_result("正在同步数据库并查询服务器状态...")

        try:
            rows = await asyncio.to_thread(self._fetch_server_list)

            if not rows:
                yield event.plain_result("数据库中没有已启用的服务器配置")
                return

            tasks = [self._query_a2s(s) for s in rows]
            results = await asyncio.gather(*tasks)

            grouped_data = {}
            total_players = 0

            for res in results:
                group = res['group']
                total_players += res['player_count']
                if group not in grouped_data:
                    grouped_data[group] = []
                grouped_data[group].append(res['line'])

            output = ["**CS2 服务器实时状态**\n"]
            for group_name, blocks in grouped_data.items():
                output.append(f"🔹 **{group_name}**")
                output.extend(blocks)
                output.append("")

            output.append(f"━━━━━━━━━━━━━━")
            output.append(f"**当前总在线人数**: `{total_players}`")

            yield event.plain_result("\n".join(output))

        except Exception as e:
            logger.error(f"CS2 Status 运行报错: {e}")
            yield event.plain_result(f"查询出错: {str(e)}")

    def _fetch_server_list(self):
        conn = self.get_db_conn()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT name, host, port, group_name FROM servers WHERE is_active = 1 ORDER BY group_name DESC")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return rows

    async def _query_a2s(self, s):
        host, port = s['host'], s['port']
        name, group = s['name'], s['group_name']
        try:
            info = await asyncio.to_thread(a2s.info, (host, port), timeout=2.0)
            line = f"**{name}** | `{info.map_name}`\n└ 👥 ({info.player_count}/{info.max_players}) `{host}:{port}`"
            return {"group": group, "line": line, "player_count": info.player_count}
        except:
            line = f"**{name}**\n└ (查询超时) `{host}:{port}`"
            return {"group": group, "line": line, "player_count": 0}
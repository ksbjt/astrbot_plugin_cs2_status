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
    "1.0.0",
)
class CS2StatusPlugin(Star):
    def __init__(self, context: Context, config: dict):
        super().__init__(context)
        # 优先使用 AstrBot 注入的 config 字典
        self.config = config if config else context.config

    def get_db_conn(self):
        """建立数据库连接"""
        return mysql.connector.connect(
            host=self.config.get("db_host", "127.0.0.1"),
            port=int(self.config.get("db_port", 3306)),
            user=self.config.get("db_user", "root"),
            password=self.config.get("db_pass", ""),
            database=self.config.get("db_name", "cs2_servers"),
            connect_timeout=5
        )

    @filter.command("status")
    async def server_status(self, event: AstrMessageEvent):
        """查询服务器状态指令: /status"""

        yield event.plain_result("正在同步数据库并查询服务器状态...")

        try:
            # 1. 获取数据库连接并查询列表
            rows = await asyncio.to_thread(self._fetch_server_list)

            if not rows:
                yield event.plain_result("数据库中没有已启用的服务器配置。")
                return

            # 2. 并行查询 A2S 接口 (提高效率)
            tasks = [self._query_a2s(s) for s in rows]
            results = await asyncio.gather(*tasks)

            # 3. 组织数据
            grouped_data = {}
            total_players = 0

            for res in results:
                group = res['group']
                total_players += res['player_count']
                if group not in grouped_data:
                    grouped_data[group] = []
                grouped_data[group].append(res['line'])

            # 4. 构建输出消息
            output = ["**CS2 服务器实时状态**\n"]
            # 按组名排序显示
            for group_name in sorted(grouped_data.keys(), reverse=True):
                output.append(f"**{group_name}**")
                output.extend(grouped_data[group_name])
                output.append("")

            output.append(f"━━━━━━━━━━━━━━")
            output.append(f"**当前总在线人数**: `{total_players}`")

            yield event.plain_result("\n".join(output))

        except Exception as e:
            logger.error(f"CS2 Status 运行报错: {e}")
            yield event.plain_result(f"查询出错: {str(e)}")

    def _fetch_server_list(self):
        """同步方法：从数据库读取列表"""
        conn = self.get_db_conn()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT name, host, port, group_name FROM servers WHERE is_active = 1 ORDER BY group_name DESC")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return rows

    async def _query_a2s(self, s):
        """异步方法：单个服务器的 A2S 查询"""
        host, port = s['host'], s['port']
        name, group = s['name'], s['group_name']
        try:
            # 使用 asyncio.to_thread 包装同步阻塞的 a2s 查询
            info = await asyncio.to_thread(a2s.info, (host, port), timeout=2.0)
            line = f"**{name}** | `{info.map_name}`\n└ ( {info.player_count} / {info.max_players} ) `{host}:{port}`"
            return {"group": group, "line": line, "player_count": info.player_count}
        except Exception:
            # 捕获 A2S 查询超时或连接失败
            line = f"**{name}**\n└ (查询超时) `{host}:{port}`"
            return {"group": group, "line": line, "player_count": 0}

    async def terminate(self):
        """插件卸载时的清理动作"""
        logger.info("CS2 服务器查询插件已卸载")
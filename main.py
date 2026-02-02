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
    "1.0.6",
)
class CS2StatusPlugin(Star):
    def __init__(self, context: Context, config: dict):
        super().__init__(context)
        self.config = config if config else context.config

    def _get_db_conn(self):
        """建立数据库连接"""
        return mysql.connector.connect(
            host=self.config.get("db_host", "127.0.0.1"),
            port=int(self.config.get("db_port", 3306)),
            user=self.config.get("db_user", "root"),
            password=self.config.get("db_pass", ""),
            database=self.config.get("db_name", "cs2_serverlist"),
            connect_timeout=5,
        )

    @filter.command("servers")
    async def server_status(self, event: AstrMessageEvent):
        """查询开水服列表信息"""

        # 修正：直接访问 event.platform 属性
        platform_name = getattr(event, "platform", "").lower()
        is_rich_platform = platform_name in ["discord", "kook", "telegram", "ai_vocational"]

        yield event.plain_result("正在同步数据库并查询服务器状态...")

        try:
            # 1. 异步获取数据库服务器列表
            rows = await asyncio.to_thread(self._fetch_server_list)

            if not rows:
                yield event.plain_result("❌ 数据库中没有已启用的服务器配置")
                return

            # 2. 并行查询 A2S 接口
            tasks = [self._query_a2s(s, is_rich_platform) for s in rows]
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

            # 如果是 Discord 等平台，加个标题
            if is_rich_platform:
                output.append("📊 **CS2 服务器实时状态**\n")

            for group_name in sorted(grouped_data.keys(), reverse=True):
                output.append(f"↓ {group_name} ↓")

                for res in grouped_data[group_name]:
                    output.append(res["line"])

                output.append("")  # 组间空行

            # 底部统计信息
            if is_rich_platform:
                output.append(f"👥 **当前总计在线**: `{total_players}` 人")
            else:
                output.append(f"总在线人数: {total_players}")

            yield event.plain_result("\n".join(output))

        except Exception as e:
            logger.error(f"CS2 Status 运行报错: {e}")
            yield event.plain_result(f"❌ 查询出错: {str(e)}")

    def _fetch_server_list(self):
        """从数据库读取列表"""
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

    async def _query_a2s(self, s, is_rich_platform: bool):
        """异步查询单个服务器，根据平台生成对应格式的行"""
        host, port = s["host"], s["port"]
        name, group = s["name"], s["group_name"]

        try:
            # 增加超时控制
            info = await asyncio.to_thread(a2s.info, (host, port), timeout=2.0)

            if is_rich_platform:
                # Discord 等富文本平台：带加粗、代码块和层级符号
                line = f"**{name}** | `{info.map_name}`\n└ ({info.player_count}/{info.max_players}) `{host}:{port}`"
            else:
                # QQ/微信等纯文本平台：简单整洁
                line = f"{name} |=> {info.map_name}\n({info.player_count} / {info.max_players}) {host}:{port}"

            return {"group": group, "line": line, "player_count": info.player_count}

        except Exception:
            if is_rich_platform:
                line = f"**{name}** | `查询超时`\n└ (0/0) `{host}:{port}`"
            else:
                line = f"{name} |=> 查询超时\n(0 / 0) {host}:{port}"
            return {"group": group, "line": line, "player_count": 0}

    async def terminate(self):
        logger.info("服务器查询插件已卸载")
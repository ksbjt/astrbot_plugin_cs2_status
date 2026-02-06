# astrbot_plugin_cs2_status

### 介绍

- 查询 CS2 服务器信息

---

### 新增数据

```mysql
CREATE DATABASE IF NOT EXISTS cs2_serverlist CHARACTER SET utf8mb4;
```

``` mysql
USE cs2_serverlist;
```

``` mysql
CREATE TABLE IF NOT EXISTS `servers` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `name` VARCHAR(100) NOT NULL COMMENT '显示名称',
    `host` VARCHAR(50) NOT NULL COMMENT 'IP地址',
    `port` INT NOT NULL COMMENT '查询端口',
    `mode` VARCHAR(50) DEFAULT '其他' COMMENT '分组名称',
    `rcon_pwd` VARCHAR(100) DEFAULT '' COMMENT 'RCON密码',
    `is_active` TINYINT(1) DEFAULT 1 COMMENT '是否启用: 1启用, 0禁用'
);
```

``` mysql
INSERT INTO servers (name, host, port, mode, is_active) VALUES 
('01#', 'ip', port, 'mode', 1),
('02#', 'ip', port, 'mode', 1),
('03#', 'ip', port, 'mode', 1);
```

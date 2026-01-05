from langgraph.checkpoint.postgres import PostgresSaver

# 定义 PostgreSQL 数据库连接 URI 和连接参数（此前先创建运行你自己的postgres容器：docker run -d -p 5442:5432 -e POSTGRES_PASSWORD=postgres postgres）
DB_URI = "postgresql://postgres:postgres@localhost:5442/postgres?sslmode=disable"
# 协议：postgresql:// 表示使用 PostgreSQL 协议。
# 用户信息：postgres:postgres 表示用户名为 postgres，密码也为 postgres。
# 主机：@localhost 表示数据库位于本地机器。
# 端口：:5442 表示数据库服务运行在 5442 端口（默认是 5432）。
# 数据库名：/postgres 表示连接的数据库名为 postgres。
# SSL 模式：?sslmode=disable 表示禁用 SSL 加密连接。

connection_kwargs = {
    "autocommit": True,  # 开启自动提交
    "prepare_threshold": 0,  # 设置预处理语句阈值
}


from psycopg_pool import ConnectionPool

with ConnectionPool(
    conninfo=DB_URI,  # 数据库连接字符串
    max_size=20,  # 连接池最大连接数
    kwargs=connection_kwargs,  # 数据库连接参数
) as pool:
    # 初始化 PostgresSaver 对象，充当App的保存器，它负责将App状态保存到Postgres数据库中。
    checkpointer = PostgresSaver(pool)
    # # 下面这条命令在初次使用该检查器时使用，在数据库中创建必要的表。
    checkpointer.setup()
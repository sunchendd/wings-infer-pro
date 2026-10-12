# G.FUU.18 禁止直接使用外部数据拼接SQL命令

- **规则ID**：1b90fc03-bb13-4995-8262-81899c302634
- **更新时间**：2025-03-25 19:23:45

---

**【问题级别】**

一般

**【描述】**

SQL注入是指SQL查询被恶意更改成一个与程序预期完全不同的查询。执行更改后的查询可能会导致信息泄露或者数据被篡改。而SQL注入的根源就是使用外部数据来拼接SQL语句。C/C++语言中常见的使用外部数据拼接SQL语句的场景有（包括但不局限于）：



连接MySQL时调用mysql_query()，Execute()时的入参

连接SQL Server时调用db-library驱动的dbsqlexec()的入参

调用ODBC驱动的SQLprepare()连接数据库时的SQL语句的参数

C++程序调用OTL类库中的otl_stream()，otl_column_desc()时的入参

C++程序连接Oracle数据库时调用ExecuteWithResSQL()的入参

防止SQL注入的方法主要有以下几种：



参数化查询（通常也叫作预处理语句）：参数化查询是一种简单有效的防止SQL注入的查询方式，应该被优先考虑使用。支持的数据库有MySQL，Oracle（OCI）。

参数化查询（通过ODBC驱动）：支持ODBC驱动参数化查询的数据库有Oracle、SQLServer、PostgreSQL和GaussDB。

对外部数据进行校验（对于每个引入的外部数据推荐“白名单”校验）。

对外部数据中的SQL特殊字符进行转义。

SQL特殊字符参见：附录A SQL注入相关的特殊字符

**【正确示例】**

```
使用预处理语句进行参数化查询可以防御SQL注入攻击：

char name[NAME_MAX];
...
MYSQL_STMT *stmt = mysql_stmt_init(myConnection);
char *query = "SELECT childinfo FROM children WHERE name= ?";
if (mysql_stmt_prepare(stmt, query, strlen(query))) {
    ...
}
int ret = GetUserInput(name, NAME_MAX);
...
MYSQL_BIND params[1];
(void)memset_s(params, sizeof(params), 0, sizeof(params));
...
params[0].bufferType = MYSQL_TYPE_STRING;
params[0].buffer = (char *)name;
params[0].bufferLength = strlen(name);
params[0].isNull = 0;

bool isCompleted = mysql_stmt_bind_param(stmt, params);
...
ret = mysql_stmt_execute(stmt);
...

```
**【错误示例】**

```
下列代码拼接用户输入，没有进行输入检查，存在SQL注入风险：

char name[NAME_MAX];
char sqlStatements[SQL_CMD_MAX];
int ret = GetUserInput(name, NAME_MAX);
...
ret = sprintf_s(sqlStatements,
                SQL_CMD_MAX,
                "SELECT childinfo FROM children WHERE name= ‘%s’",
                name);
...
ret = mysql_query(&myConnection, sqlStatements);
...

```
**【修复建议】**

输入校验包括但不局限于： 校验数据长度校验数据范围校验数据类型和格式校验输入只包含可接受的字符（“白名单”形式），尤其需要注意一些特殊情况下的特殊字符。

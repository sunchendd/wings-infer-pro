# SecS_Query_String_Injection

- **规则ID**：d089b56d-a40f-4a3b-aaf6-3287103f840a
- **更新时间**：2026-04-07 04:00:02

---

**【问题级别】**

严重

**【描述】**

SQL注入是一种网络安全漏洞，攻击者通过在应用程序的输入框中插入恶意的SQL代码，来干扰应用程序对其数据库的正常查询。这种攻击方式主要利用了设计不良的程序在处理用户输入时忽略了字符检查的弱点，从而使得注入的恶意指令被数据库服务器误认为是正常指令并执行。



SQL注入错误在以下情况下发生：



1. 数据从一个不可信赖的数据源进入程序；



2. 数据用于动态地构造一个 SQL 查询。

**【正确示例】**

```
```java

@Override

public void doPost(HttpServletRequest request, HttpServletResponse response) throws ServletException, IOException

{

String data = request.getParameter("username");

//... 其他代码

Connection dbConnection = null;

Statement sqlStatement = null;

dbConnection = IO.getDBConnection();

sqlStatement = dbConnection.createStatement();

// 【GOOD】 对SQL使用数据进行校验

if(invalidSql(data))

{

return;

}

String sql = "insert into users (status) values ('updated') where name='" + data + "'";

boolean result = sqlStatement.execute(sql);

//... 其他代码

}

```

```
**【错误示例】**

```
```java

@Override

public void doPost(HttpServletRequest request, HttpServletResponse response) throws ServletException, IOException

{

String data = request.getParameter("username");

//... 其他代码

Connection dbConnection = null;

Statement sqlStatement = null;

dbConnection = IO.getDBConnection();

sqlStatement = dbConnection.createStatement();

//  【不符合】: data 由外部输入，存在注入风险

String sql = "insert into users (status) values ('updated') where name='" + data + "'";

boolean result = sqlStatement.execute(sql);

//... 其他代码

}

```

```
**【修复建议】**

防护措施主要有以下三类：



+ 使用参数化查询：最有效的防护手段，但对SQL语句中的表名、字段名等不适用；



+ 对外部数据进行白名单校验：适用于拼接SQL语句中的表名、字段名；



+ 对外部数据中的与SQL注入相关的特殊字符（参考附录A）进行转义：适用于必须通过字符串拼接构造SQL语句的场景，转义仅对由引号限制的字段有效。

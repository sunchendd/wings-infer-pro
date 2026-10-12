# G.EDV.06 禁止直接使用外部数据来拼接SQL语句

- **规则ID**：d6c17c6a-c28f-411e-98be-c62142e17fb1
- **更新时间**：2026-04-07 04:15:04

---

**【问题级别】**

严重

**【描述】**

如果直接使用外部数据来拼接SQL语句，攻击者可以通过在输入框中输入恶意的SQL语句来执行任意的SQL操作，从而导致信息泄露或者数据被篡改。

因此，为了保证数据库的安全性，禁止直接使用外部数据来拼接SQL语句。

**【正确示例】**

```
##### 场景1：

- 修复示例：对外部数据进行校验

对于字符型的字段进行处理时，要对输入做转义，将单引号替换为两个单引号。

```python
import sqlite3
import sys


def string_verify(input_str):
    # 将单引号替换为两个单引号
    verified_str = input_str.replace("'", "''")
    return verified_str


def good():
    conn = sqlite3.connect("e:/test_sqlite3.db")
    con_cursor = conn.cursor()

    # SOURCE：read data from system
    username = sys.argv[0]
    # 校验外部数据
    verified_username = string_verify(username)
    cmd = "select * from COMPANY where NAME = '{:s}'".format(verified_username)
    # SINK: data concatenated into SQL statement used in execute(), which could result in SQL Injection
    con_cursor.execute(cmd)  # 符合

    conn.commit()
    conn.close()
```

```
**【错误示例】**

```
##### 场景1：

- 错误示例：直接使用外部数据拼接SQL语句

```python
import sqlite3
import sys


def bad():
    conn = sqlite3.connect("e:/test_sqlite3.db")
    con_cursor = conn.cursor()

    # SOURCE：read data from system
    username = sys.argv[0]
    # 直接使用外部数据拼接SQL语句
    cmd = "select * from COMPANY where NAME = '{:s}'".format(username)
    # SINK: data concatenated into SQL statement used in execute(), which could result in SQL Injection
    con_cursor.execute(cmd)  # 不符合

    conn.commit()
    conn.close()
```
  
如果username获取到字符串为`A' or 1=1 -- `，最终拼接的SQL语句为：
  
```sql
select * from COMPANY where NAME = 'A' or 1=1 --'
```
  
该SQL语句被注入后，会导致所有的数据被返回到结果集中，使攻击者非法绕过。

```
**【修复建议】**

SQL注入产生的根本原因是使用外部数据直接拼接SQL语句，防护措施主要有以下三类：

1. 使用参数化查询：最有效的防护手段。

2. 对外部数据进行白名单校验。

3. 对外部数据中的与SQL注入相关的特殊字符进行转义：适用于必须通过字符串拼接构造SQL语句的场景，转义仅对由引号限制的字段有效。

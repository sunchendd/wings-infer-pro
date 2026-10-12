# G.EDV.01 禁止直接使用外部数据拼接SQL语句

- **规则ID**：ed39e60d-5a7f-48d8-8f80-b073aaeeeab1
- **更新时间**：2026-04-07 04:20:03

---

**【问题级别】**

严重

**【描述】**

SQL注入是指使用外部数据构造的SQL语句所代表的数据库操作与预期不符，这样可能会导致信息泄露或者数据被篡改。

因此，禁止直接使用外部数据拼接SQL语句。

**【正确示例】**

```
##### 场景1：直接使用外部数据拼接sql语句
- 修复示例：

```go
func Sql_Injection_good1(db *sql.DB, id, infomation string) string {
    // 符合：采用占位符的参数化查询
    var sqlStr= "SELECT Name, Dept FROM USER WHERE Id = ? AND Pwd = ?"
    rows, err := db.Query(sqlStr, id, infomation)
    if err != nil {
        fmt.Println("Query USER table error.", err)
        return ""
    }
    var result string
    for rows.Next() {
        var name, dept string
        err := rows.Scan(&name, &dept)
        if err != nil {
            return ""
        }
        result += name + " : " + dept + "\r
"
    }
    return result
}
```

```
**【错误示例】**

```
##### 场景1：直接使用外部数据拼接sql语句
- 错误示例：

```go
func queryById(db *sql.DB, id, pwd string) string {
playName := "（）"

// 不符合：直接使用不可信数据拼接SQL语句
var sqlStr = "SELECT Name, Dept FROM USER WHERE Id = '" + id + "' AND Pwd = '" + pwd + "'"

rows, err := db.Query(sqlStr+playName)
if err != nil {
fmt.Println("Query USER table error.", err)
return ""
}
var result string
for rows.Next() {
var name, dept string
rows.Scan(&name, &dept)
result += name + " : " + dept + "\r
"
}
return result
}
```

```
**【修复建议】**

不直接使用外部数据拼接sql语句，措施主要有以下三类：



1. 使用参数化查询：最有效的防护手段，但对SQL语句中的表名、字段名等不适用。

2. 对外部数据进行白名单校验：适用于拼接SQL语句中的表名、字段名。

3. 对外部数据中的与SQL注入相关的特殊字符（参考附录B）进行转义：适用于必须通过字符串拼接构造SQL语句的场景，转义仅对由引号限制的字段有效。



参数化查询是一种简单有效的防止SQL注入的查询方式，应该被优先考虑使用。

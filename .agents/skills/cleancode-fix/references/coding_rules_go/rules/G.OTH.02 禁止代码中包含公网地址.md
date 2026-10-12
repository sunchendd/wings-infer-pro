# G.OTH.02 禁止代码中包含公网地址

- **规则ID**：5fd17dd9-ec7d-4321-95e8-c2b2fbec8088
- **更新时间**：2026-04-07 04:20:03

---

**【问题级别】**

一般

**【描述】**

代码中硬编码公网IP地址，即不利于维护，也会导致信息泄露。

因此，禁止硬编码公网IP地址。

**【正确示例】**

```
##### 场景1：硬编码Ipv4公网地址。
- 修复示例：公网地址可以存储在配置文件或数据库中，通过读取配置文件或数据库来获取信息。

    ```go
    // 如果IP地址存储到数据库中，可通过查询操作获取数据
    ...
    rows, err := db.Query("SELECT ip FROM table_name")
    if err != nil {
        fmt.Println("Query USER table error.", err)
        return ""
    }
    defer rows.Close()

    // 遍历查询结果
    for rows.Next() {
        var ip string
        err := rows.Scan(&ip) // 符合：从数据库来获取IP地址
        if err != nil {
            fmt.Println("Query Scan error.", err)
        }
        ...
    }
    ...
    ```
##### 场景2：硬编码Ipv6公网地址。
- 修复示例：公网地址可以存储在配置文件或数据库中，通过读取配置文件或数据库来获取信息。

    ```go
    // 如果IP地址存储到数据库中，可通过查询操作获取数据
    ...
    rows, err := db.Query("SELECT ip FROM table_name")
    if err != nil {
        fmt.Println("Query USER table error.", err)
        return ""
    }
    defer rows.Close()

    // 遍历查询结果
    for rows.Next() {
        var ip string
        err := rows.Scan(&ip) // 符合：从数据库来获取IP地址
        if err != nil {
            fmt.Println("Query Scan error.", err)
        }
        ...
    }
    ...
    ```


```
**【错误示例】**

```
##### 场景1：硬编码Ipv4公网地址。
- 错误示例：

    ```go
    ip := "128.0.0.1:100" // 不符合： 硬编码IP地址
    ```
##### 场景2：硬编码Ipv6公网地址。
- 错误示例：

    ```go
    ip := "fa80:0:0:ec61:c1d1:9827:82be:3" // 不符合： 硬编码IP地址
    ```


```
**【修复建议】**

禁止硬编码公网地址，可以存储在配置文件或数据库中，通过读取配置文件或数据库来获取信息。

对于开源/第三方软件自带的公网地址必须至少禁止硬编码包含用户界面不可见、或产品资料未描述的未公开的公网地址。

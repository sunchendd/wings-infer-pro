# G.FIO.05 禁止直接使用外部数据构造格式化字符串

- **规则ID**：7ea8c4e7-6e62-4d09-ac19-dab88fdf1e4e
- **更新时间**：2026-04-07 04:20:01

---

**【问题级别】**

严重

**【描述】**

如果格式化字符串含有外部数据，攻击者可通过格式化字符串注入引起信息泄露或者拒绝服务攻击。

因此，禁止直接使用外部数据构造格式化字符串。

**【正确示例】**

```
##### 场景1：在格式化函数中使用外部数据构造的格式化字符串。
- 修复示例：用Println()来代替Printf()函数，Println()会直接将参数的内容输出，而不是去按格式化解析输入。

    ```go
    func IncorrectPassword(user string) {
        msgFormat := "%s cannot be authenticated.
"
        msg := fmt.Sprintf(msgFormat, user)
        fmt.Println(msg) // 符合： 使用Println函数代替Printf函数
    }
    ```


```
**【错误示例】**

```
##### 场景1：在格式化函数中使用外部数据构造的格式化字符串。
- 错误示例：

    ```go
    func IncorrectPassword(user string) {
        msgFormat := "%s cannot be authenticated.
"
        msg := fmt.Sprintf(msgFormat, user)
        fmt.Printf(msg) // 不符合： msg中有来自未验证的外部数据，存在格式化漏洞
    }
    ```


```
**【修复建议】**

1. 禁止在`Printf`、`Fprintf`、`Sprintf`等函数中使用外部数据构造的格式化字符串。

2. 如果要将外部数据构造的字符串内容输出，可使用`Println`函数，Println()会直接将参数的内容输出，而不是去按格式化解析输入。

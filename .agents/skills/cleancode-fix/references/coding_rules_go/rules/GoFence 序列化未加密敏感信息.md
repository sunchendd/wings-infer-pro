# GoFence 序列化未加密敏感信息

- **规则ID**：97c7926b-3b5c-413a-bb82-a6bfba4e2caf
- **更新时间**：2026-04-07 04:20:03

---

**【问题级别】**

一般

**【描述】**

虽然序列化可以将对象的状态保存为一个字节序列，之后通过反序列化该字节序列又能重新构造出原来的对象，但是它并没有提供一种机制来保证序列化数据的安全性。可访问序列化数据的攻击者可以借此获取敏感信息并确定对象的实现细节。攻击者也可恶意修改其中的数据，试图在其被反序列化之后对系统造成危害。敏感数据序列化之后是潜在对外暴露着的，因此序列化信息中不应该包括：密钥、数字证书、以及那些在序列化时引用敏感数据的类。

防止敏感数据被无意识的序列化导致敏感信息泄露

**【正确示例】**

```
```
type CreditCard struct {
    Id     int    `json:"card_id"`
    Bank   string `json:"bank_name"`
    Owner  string `json:"owner_id"`
    Passwd string `json:"-"` // 正确：声明Paaswd敏感信息不被序列化
}

func main() {
    var card CreditCard
    card.Id = 132004473002056
    card.Bank = "China bank"
    card.Owner = "golang"
    card.Passwd = "Tell4U" // 口令不能硬编码在代码中，这里只是为了程序演示
    // 序列化
    serialStr, err := json.Marshal(card)
    if err != nil {
        fmt.Println("Serialization error.")
        return
    }
    fmt.Println(string(serialStr), err)

    // 发送给接收方

    // 后面代码略……

}
```

```
**【错误示例】**

```
```
type CreditCard struct {
    Id     int    `json:"card_id"`
    Bank   string `json:"bank_name"`
    Owner  string `json:"owner_id"`
    Passwd string `json:"password"` // 敏感信息
}

func main() {
    var card CreditCard
    card.Id = 132004473002056
    card.Bank = "China bank"
    card.Owner = "golang"
    card.Passwd = "Tell4U" // 口令不能硬编码在代码中，这里只是为了程序演示
    // 序列化
    serialStr, err := json.Marshal(card) // 错误：直接将敏感信息序列化
    if err != nil {
        fmt.Println("Serialization error.")
        return
    }
    fmt.Println(string(serialStr), err)
    // 发送给接收方
    // 后面代码略……
}
```

```
**【修复建议】**

阻止包含敏感信息的数据成员被序列化，以及不可序列化或者敏感对象的引用被序列化----------------参考华为go语言安全编程规范2.1

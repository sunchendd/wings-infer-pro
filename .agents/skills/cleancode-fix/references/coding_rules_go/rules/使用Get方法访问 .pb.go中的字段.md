# 使用Get方法访问 .pb.go中的字段

- **规则ID**：aa910f7f-7f36-44d2-bd03-f189e36bd4ff
- **更新时间**：2026-04-07 04:20:01

---

**【问题级别】**

一般

**【描述】**

由于protobuf工具生成的.pb.go代码大多被用于不同服务间的消息传输，由于这个特点，pb代码中的结构体指针成员需要执行判空再访问其子成员，Get方法中有相应的检查，pb.go里的字段都得用Getxx方法访问 不能直接读。

**【正确示例】**

```
```go
func testAccessFieldInMMFile() {
    in, err := ioutil.ReadFile("./address_book.txt")
    if err != nil {
        log.Fatalln("Error reading file:", err)
    }
    book := tutorialmm.AddressBook{}
    if err := proto.Unmarshal(in, &book); err != nil {
        log.Fatalln("Failed to parse address book:", err)
    }
    for _, p := range book.GetPeople() {
        p.Name = ""              // ok
        fmt.Println(p.GetName()) // 正确：用Getxx方法访问
    }
}

```
**【错误示例】**

```
```go
func testAccessFieldInMMFile() {
    in, err := ioutil.ReadFile("./address_book.txt")
    if err != nil {
        log.Fatalln("Error reading file:", err)
    }
    book := tutorialmm.AddressBook{}
    if err := proto.Unmarshal(in, &book); err != nil {
        log.Fatalln("Failed to parse address book:", err)
    }
    for _, p := range book.GetPeople() {
        p.Name = ""              // ok
        fmt.Println(p.Name)      //错误：直接访问

    }
}

```
**【修复建议】**

建议使用Get方法访问 .pb.go中的字段

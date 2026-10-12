# GoFence 默认CSV注入检测规则

- **规则ID**：c3ff2aae-0d36-456e-89d8-e478dc83b251
- **更新时间**：2026-04-07 04:20:03

---

**【问题级别】**

一般

**【描述】**

CSV注入：也称为公式注入，是在将内容已csv的方式导出到一个文件时，由于特殊字符经过特殊处理，直接输出到csv文件导致的注入。

**【正确示例】**

```
```
func CsvInjectByWriteAll(inject string) {
         inject:= checkAndEncode(inject) // 正确：校验外部输入
record := [][]string{{"first_name", "last_name", "username"}, {"Rob", "Pike", "rob"}, {"Ken", "Thompson", inject}}
    f, err := os.Create("test.csv")
    if err != nil {
        panic(err)
    }
    w := csv.NewWriter(f)

    err = w.WriteAll(record) 
    if err != nil {
        log.Fatalln("error writing csv:", err)
        return
    }
    err = f.Close()
    if err != nil {
        log.Fatalln("error close csv file:", err)
    }
}
```

```
**【错误示例】**

```
```
func CsvInjectByWriteAll(inject string) {
record := [][]string{{"first_name", "last_name", "username"}, {"Rob", "Pike", "rob"}, {"Ken", "Thompson", inject}}
    f, err := os.Create("test.csv")
    if err != nil {
        panic(err)
    }
    w := csv.NewWriter(f)
    err = w.WriteAll(record) // 错误：未校验外部输入
    if err != nil {
        log.Fatalln("error writing csv:", err)
        return
    }
    err = f.Close()
    if err != nil {
        log.Fatalln("error close csv file:", err)
    }
}
```

```
**【修复建议】**

通常可以用双引号将特殊符号引起来，比如 =SUM(1,2) -> "=SUM(1,2)"

外部输入进行有效验证，防止数据注入问题 --------参考go分析与 安全测试
